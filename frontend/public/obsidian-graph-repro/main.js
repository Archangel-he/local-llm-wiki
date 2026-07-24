const canvas = document.querySelector("#graph");
const context = canvas.getContext("2d");
const statusEl = document.querySelector("#status");
const worker = new Worker(new URL("./sim-worker.js", import.meta.url), {
  type: "module",
  name: "Graph Worker",
});

const nodeDefinitions = [
  ["Knowledge", 18],
  ["Ideas", 12],
  ["Projects", 13],
  ["Research", 11],
  ["Writing", 10],
  ["Books", 8],
  ["Notes", 16],
  ["Questions", 7],
  ["Design", 9],
  ["Code", 10],
  ["People", 6],
  ["Archive", 5],
  ["Daily", 8],
  ["Experiments", 7],
].map(([id, weight], index) => ({
  id,
  weight,
  x: Math.cos((index / 14) * Math.PI * 2) * 180 + Math.random() * 30,
  y: Math.sin((index / 14) * Math.PI * 2) * 180 + Math.random() * 30,
}));

const links = [
  ["Knowledge", "Ideas"],
  ["Knowledge", "Research"],
  ["Knowledge", "Notes"],
  ["Ideas", "Projects"],
  ["Ideas", "Writing"],
  ["Ideas", "Design"],
  ["Projects", "Code"],
  ["Projects", "Experiments"],
  ["Research", "Books"],
  ["Research", "Questions"],
  ["Writing", "Books"],
  ["Writing", "Daily"],
  ["Notes", "Daily"],
  ["Notes", "Archive"],
  ["Notes", "People"],
  ["Design", "Experiments"],
  ["Code", "Experiments"],
  ["Questions", "People"],
];

const neighbors = new Map(nodeDefinitions.map((node) => [node.id, new Set()]));
for (const [source, target] of links) {
  neighbors.get(source).add(target);
  neighbors.get(target).add(source);
}

const nodes = new Map(
  nodeDefinitions.map((node) => [
    node.id,
    {
      ...node,
      targetX: node.x,
      targetY: node.y,
    },
  ]),
);

const camera = {
  x: 0,
  y: 0,
  scale: 1,
};

let deviceScale = window.devicePixelRatio || 1;
let rafHandle = null;
let idleFrames = 0;
let hoveredNode = null;
let draggedNode = null;
let panning = false;
let lastPointer = null;
let latestAlpha = 1;
let autoFit = true;
let renderedFocusNode = null;
let focusBlend = 0;
let previousRenderTime = performance.now();

function resize() {
  deviceScale = window.devicePixelRatio || 1;
  canvas.width = Math.round(innerWidth * deviceScale);
  canvas.height = Math.round(innerHeight * deviceScale);
  canvas.style.width = `${innerWidth}px`;
  canvas.style.height = `${innerHeight}px`;
  fitCameraToNodes();
  changed();
}

function graphToScreen(node) {
  return {
    x: innerWidth / 2 + camera.x + node.x * camera.scale,
    y: innerHeight / 2 + camera.y + node.y * camera.scale,
  };
}

function screenToGraph(x, y) {
  return {
    x: (x - innerWidth / 2 - camera.x) / camera.scale,
    y: (y - innerHeight / 2 - camera.y) / camera.scale,
  };
}

function nodeRadius(node) {
  const sizeScale = Number(document.querySelector("#node-size").value);
  return Math.max(4, Math.min(3 * Math.sqrt(node.weight + 1), 30) * sizeScale);
}

function distancesFrom(startId) {
  const distances = new Map([[startId, 0]]);
  const queue = [startId];

  for (let index = 0; index < queue.length; index += 1) {
    const current = queue[index];
    const distance = distances.get(current);
    if (distance >= 2) continue;

    for (const neighbor of neighbors.get(current)) {
      if (distances.has(neighbor)) continue;
      distances.set(neighbor, distance + 1);
      queue.push(neighbor);
    }
  }

  return distances;
}

function mixChannels(from, to, amount) {
  return from.map((value, index) =>
    Math.round(value + (to[index] - value) * amount),
  );
}

function rgba(channels, opacity) {
  return `rgba(${channels.join(", ")}, ${opacity})`;
}

function fitCameraToNodes() {
  if (nodes.size === 0) return;

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const node of nodes.values()) {
    minX = Math.min(minX, node.x);
    maxX = Math.max(maxX, node.x);
    minY = Math.min(minY, node.y);
    maxY = Math.max(maxY, node.y);
  }

  const padding = 64;
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  const availableWidth = Math.max(1, innerWidth - padding * 2);
  const availableHeight = Math.max(1, innerHeight - padding * 2);

  camera.scale = Math.max(
    0.2,
    Math.min(4, availableWidth / width, availableHeight / height),
  );
  camera.x = -((minX + maxX) / 2) * camera.scale;
  camera.y = -((minY + maxY) / 2) * camera.scale;
}

function findNodeAt(x, y) {
  let best = null;
  let bestDistance = Infinity;

  for (const node of nodes.values()) {
    const point = graphToScreen(node);
    const dx = point.x - x;
    const dy = point.y - y;
    const distance = Math.hypot(dx, dy);
    const radius = nodeRadius(node) * Math.sqrt(1 / camera.scale) * camera.scale + 5;

    if (distance <= radius && distance < bestDistance) {
      best = node;
      bestDistance = distance;
    }
  }

  return best;
}

function queueRender() {
  if (rafHandle === null) {
    rafHandle = requestAnimationFrame(render);
  }
}

function changed() {
  idleFrames = 0;
  queueRender();
}

function render() {
  rafHandle = null;
  if (idleFrames > 60) return;

  const now = performance.now();
  const elapsed = Math.min(64, now - previousRenderTime);
  previousRenderTime = now;
  const requestedFocus = draggedNode || hoveredNode;
  if (requestedFocus && requestedFocus !== renderedFocusNode) {
    renderedFocusNode = requestedFocus;
    focusBlend = 0;
  }
  const focusTarget = requestedFocus ? 1 : 0;
  focusBlend +=
    (focusTarget - focusBlend) * (1 - Math.exp(-elapsed / 70));
  if (!requestedFocus && focusBlend < 0.005) {
    renderedFocusNode = null;
    focusBlend = 0;
  }
  const distances = renderedFocusNode
    ? distancesFrom(renderedFocusNode.id)
    : null;
  const grayNode = [82, 82, 89];
  const purpleNode = [124, 110, 230];

  context.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
  context.clearRect(0, 0, innerWidth, innerHeight);
  context.lineCap = "round";

  for (const [sourceId, targetId] of links) {
    const source = nodes.get(sourceId);
    const target = nodes.get(targetId);
    const a = graphToScreen(source);
    const b = graphToScreen(target);
    const directlyConnected =
      renderedFocusNode &&
      (renderedFocusNode.id === source.id ||
        renderedFocusNode.id === target.id);
    const sourceDistance = distances?.get(source.id) ?? Infinity;
    const targetDistance = distances?.get(target.id) ?? Infinity;
    const outerDistance = Math.max(sourceDistance, targetDistance);
    let focusedOpacity = 0;
    if (directlyConnected) focusedOpacity = 0.92;
    else if (outerDistance <= 1) focusedOpacity = 0.18;
    else if (outerDistance <= 2) focusedOpacity = 0.07;
    const opacity = renderedFocusNode
      ? 0.3 + (focusedOpacity - 0.3) * focusBlend
      : 0.3;
    const edgeChannels = directlyConnected
      ? mixChannels([100, 100, 108], purpleNode, focusBlend)
      : [100, 100, 108];

    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.strokeStyle = rgba(edgeChannels, opacity);
    context.lineWidth = directlyConnected ? 1 + focusBlend * 0.8 : 1;
    context.stroke();
  }

  let allNodesVisible = true;
  for (const node of nodes.values()) {
    const point = graphToScreen(node);
    const radius = nodeRadius(node) * Math.sqrt(1 / camera.scale) * camera.scale;
    const distance = distances?.get(node.id) ?? Infinity;
    const active = node === renderedFocusNode;
    let focusedOpacity = 0;
    if (distance <= 1) focusedOpacity = 1;
    else if (distance === 2) focusedOpacity = 0.2;
    const opacity = renderedFocusNode
      ? 1 + (focusedOpacity - 1) * focusBlend
      : 1;
    const fillChannels = active
      ? mixChannels(grayNode, purpleNode, focusBlend)
      : grayNode;
    if (
      point.x - radius < 0 ||
      point.x + radius > innerWidth ||
      point.y - radius < 0 ||
      point.y + radius > innerHeight
    ) {
      allNodesVisible = false;
    }

    context.beginPath();
    context.arc(point.x, point.y, radius, 0, Math.PI * 2);
    context.fillStyle = rgba(fillChannels, opacity);
    context.shadowColor =
      active && focusBlend > 0.05
        ? rgba(purpleNode, 0.3 * focusBlend)
        : "transparent";
    context.shadowBlur = active ? 10 * focusBlend : 0;
    context.fill();
    context.shadowBlur = 0;

    context.font = `${active ? 600 : 450} 12px Inter, system-ui, sans-serif`;
    context.textAlign = "center";
    context.textBaseline = "top";
    context.fillStyle = active
      ? rgba([48, 45, 65], opacity)
      : rgba([55, 55, 62], opacity * 0.78);
    context.fillText(node.id, point.x, point.y + radius + 6);
  }
  canvas.dataset.allNodesVisible = String(allNodesVisible);
  canvas.dataset.focusedNode = renderedFocusNode?.id ?? "";
  canvas.dataset.focusStrength = focusBlend.toFixed(2);
  canvas.dataset.nodeSize = document.querySelector("#node-size").value;

  statusEl.textContent =
    `alpha ${latestAlpha.toFixed(4)} · ` +
    `${nodes.size} nodes · ${links.length} links · ` +
    (latestAlpha > 0.001 ? "simulation running" : "simulation sleeping");

  idleFrames += 1;
  queueRender();
}

function currentForces() {
  return {
    centerStrength: Number(document.querySelector("#center").value),
    repelStrength: Number(document.querySelector("#repel").value),
    linkStrength: Number(document.querySelector("#link-strength").value),
    linkDistance: Number(document.querySelector("#link-distance").value),
  };
}

function sendInitialGraph() {
  worker.postMessage({
    nodes: [...nodes.values()].map(({ id, x, y }) => ({ id, x, y })),
    links,
    forces: currentForces(),
    alpha: 1,
    alphaTarget: 0,
    run: true,
  });
}

worker.addEventListener("message", (event) => {
  const { ids, buffer, alpha } = event.data;
  const coordinates = new Float32Array(buffer);

  for (let index = 0; index < ids.length; index += 1) {
    const node = nodes.get(ids[index]);
    if (!node) continue;
    node.x = coordinates[index * 2];
    node.y = coordinates[index * 2 + 1];
  }

  latestAlpha = alpha;
  if (autoFit) {
    fitCameraToNodes();
    if (alpha <= 0.001) autoFit = false;
  }
  changed();
});

worker.addEventListener("error", (error) => {
  statusEl.textContent = `Worker error: ${error.message}`;
});

canvas.addEventListener("pointerdown", (event) => {
  autoFit = false;
  const node = findNodeAt(event.clientX, event.clientY);
  canvas.setPointerCapture(event.pointerId);
  lastPointer = { x: event.clientX, y: event.clientY };

  if (node) {
    draggedNode = node;
    canvas.classList.add("dragging");
    const position = screenToGraph(event.clientX, event.clientY);
    worker.postMessage({
      alpha: 0.3,
      alphaTarget: 0.3,
      run: true,
      forceNode: { id: node.id, ...position },
    });
  } else {
    panning = true;
  }

  changed();
});

canvas.addEventListener("pointermove", (event) => {
  if (draggedNode) {
    const position = screenToGraph(event.clientX, event.clientY);
    draggedNode.x = position.x;
    draggedNode.y = position.y;
    worker.postMessage({
      alpha: 0.3,
      alphaTarget: 0.3,
      run: true,
      forceNode: { id: draggedNode.id, ...position },
    });
    changed();
    return;
  }

  if (panning && lastPointer) {
    camera.x += event.clientX - lastPointer.x;
    camera.y += event.clientY - lastPointer.y;
    lastPointer = { x: event.clientX, y: event.clientY };
    changed();
    return;
  }

  const nextHovered = findNodeAt(event.clientX, event.clientY);
  if (nextHovered !== hoveredNode) {
    hoveredNode = nextHovered;
    changed();
  }
});

function releasePointer(event) {
  if (draggedNode) {
    worker.postMessage({
      alphaTarget: 0,
      forceNode: { id: draggedNode.id, x: null, y: null },
    });
  }

  draggedNode = null;
  panning = false;
  lastPointer = null;
  canvas.classList.remove("dragging");
  if (canvas.hasPointerCapture(event.pointerId)) {
    canvas.releasePointerCapture(event.pointerId);
  }
  changed();
}

canvas.addEventListener("pointerup", releasePointer);
canvas.addEventListener("pointercancel", releasePointer);
canvas.addEventListener("pointerleave", () => {
  if (draggedNode || panning) return;
  hoveredNode = null;
  changed();
});

canvas.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    autoFit = false;
    const before = screenToGraph(event.clientX, event.clientY);
    camera.scale = Math.max(
      0.2,
      Math.min(4, camera.scale * Math.pow(1.5, -event.deltaY / 240)),
    );
    const after = screenToGraph(event.clientX, event.clientY);
    camera.x += (after.x - before.x) * camera.scale;
    camera.y += (after.y - before.y) * camera.scale;
    changed();
  },
  { passive: false },
);

for (const input of document.querySelectorAll('input[type="range"]')) {
  const output = document.querySelector(`output[for="${input.id}"]`);
  const format = () => {
    output.value =
      input.step.includes(".") ? Number(input.value).toFixed(2) : input.value;
  };
  format();

  input.addEventListener("input", () => {
    format();
    worker.postMessage({
      forces: currentForces(),
      alpha: 0.3,
      run: true,
    });
    changed();
  });
}

document.querySelector("#reheat").addEventListener("click", () => {
  worker.postMessage({ alpha: 1, alphaTarget: 0, run: true });
  changed();
});

document.querySelector("#reset").addEventListener("click", () => {
  autoFit = true;
  camera.x = 0;
  camera.y = 0;
  camera.scale = 1;

  nodeDefinitions.forEach((definition, index) => {
    const angle = (index / nodeDefinitions.length) * Math.PI * 2;
    definition.x = Math.cos(angle) * 180;
    definition.y = Math.sin(angle) * 180;
    const node = nodes.get(definition.id);
    node.x = definition.x;
    node.y = definition.y;
  });

  sendInitialGraph();
  changed();
});

addEventListener("resize", resize);
resize();
sendInitialGraph();
