const nodesById = new Map();
let nodes = [];
let links = [];
let timer = null;

let alpha = 1;
let alphaTarget = 0;
const alphaDecay = 1 - Math.pow(0.001, 1 / 300);

const forces = {
  centerStrength: 0.1,
  repelStrength: 1000,
  linkStrength: 1,
  linkDistance: 180,
};

function rebuildLinks(linkPairs) {
  const degree = new Map(nodes.map((node) => [node.id, 0]));

  for (const [sourceId, targetId] of linkPairs) {
    degree.set(sourceId, (degree.get(sourceId) || 0) + 1);
    degree.set(targetId, (degree.get(targetId) || 0) + 1);
  }

  links = linkPairs
    .map(([sourceId, targetId]) => {
      const source = nodesById.get(sourceId);
      const target = nodesById.get(targetId);
      if (!source || !target) return null;

      const sourceDegree = degree.get(sourceId);
      const targetDegree = degree.get(targetId);
      return {
        source,
        target,
        bias: sourceDegree / (sourceDegree + targetDegree),
        strength: 1 / Math.min(sourceDegree, targetDegree),
      };
    })
    .filter(Boolean);
}

function applyCenterForce() {
  for (const node of nodes) {
    node.vx += -node.x * forces.centerStrength * alpha;
    node.vy += -node.y * forces.centerStrength * alpha;
  }
}

function applyLinkForce() {
  for (const link of links) {
    let dx =
      link.target.x +
      link.target.vx -
      link.source.x -
      link.source.vx;
    let dy =
      link.target.y +
      link.target.vy -
      link.source.y -
      link.source.vy;

    if (dx === 0 && dy === 0) {
      dx = (Math.random() - 0.5) * 1e-6;
      dy = (Math.random() - 0.5) * 1e-6;
    }

    const distance = Math.hypot(dx, dy);
    const amount =
      ((distance - forces.linkDistance) / distance) *
      alpha *
      forces.linkStrength *
      link.strength;

    dx *= amount;
    dy *= amount;

    link.target.vx -= dx * link.bias;
    link.target.vy -= dy * link.bias;
    link.source.vx += dx * (1 - link.bias);
    link.source.vy += dy * (1 - link.bias);
  }
}

function applyRepulsion() {
  const minimumDistanceSquared = 30 * 30;

  for (let left = 0; left < nodes.length; left += 1) {
    for (let right = left + 1; right < nodes.length; right += 1) {
      const a = nodes[left];
      const b = nodes[right];
      let dx = b.x + b.vx - a.x - a.vx;
      let dy = b.y + b.vy - a.y - a.vy;
      let distanceSquared = dx * dx + dy * dy;

      if (distanceSquared === 0) {
        dx = (Math.random() - 0.5) * 1e-6;
        dy = (Math.random() - 0.5) * 1e-6;
        distanceSquared = dx * dx + dy * dy;
      }

      distanceSquared = Math.max(distanceSquared, minimumDistanceSquared);
      const amount = (forces.repelStrength * alpha) / distanceSquared;

      a.vx -= dx * amount;
      a.vy -= dy * amount;
      b.vx += dx * amount;
      b.vy += dy * amount;
    }
  }
}

function applyCollision() {
  const collisionRadius = 60;
  const collisionStrength = 0.5;

  for (let left = 0; left < nodes.length; left += 1) {
    for (let right = left + 1; right < nodes.length; right += 1) {
      const a = nodes[left];
      const b = nodes[right];
      let dx = b.x + b.vx - a.x - a.vx;
      let dy = b.y + b.vy - a.y - a.vy;
      let distance = Math.hypot(dx, dy);

      if (distance === 0) {
        dx = (Math.random() - 0.5) * 1e-6;
        dy = (Math.random() - 0.5) * 1e-6;
        distance = Math.hypot(dx, dy);
      }

      if (distance >= collisionRadius) continue;

      const amount =
        ((collisionRadius - distance) / distance) * collisionStrength;
      const offsetX = dx * amount * 0.5;
      const offsetY = dy * amount * 0.5;

      a.vx -= offsetX;
      a.vy -= offsetY;
      b.vx += offsetX;
      b.vy += offsetY;
    }
  }
}

function integrate() {
  for (const node of nodes) {
    if (node.fx == null) {
      node.vx *= 0.6;
      node.x += node.vx;
    } else {
      node.x = node.fx;
      node.vx = 0;
    }

    if (node.fy == null) {
      node.vy *= 0.6;
      node.y += node.vy;
    } else {
      node.y = node.fy;
      node.vy = 0;
    }
  }
}

function publishCoordinates() {
  const ids = [];
  const buffer = new ArrayBuffer(nodes.length * 2 * Float32Array.BYTES_PER_ELEMENT);
  const coordinates = new Float32Array(buffer);

  nodes.forEach((node, index) => {
    ids.push(node.id);
    coordinates[index * 2] = node.x;
    coordinates[index * 2 + 1] = node.y;
  });

  postMessage({ ids, buffer, alpha }, [buffer]);
}

function tick() {
  timer = null;
  if (alpha <= 0.001) {
    publishCoordinates();
    return;
  }

  schedule();
  if (nodes.length === 0) return;

  alpha += (alphaTarget - alpha) * alphaDecay;
  applyCenterForce();
  applyLinkForce();
  applyRepulsion();
  applyCollision();
  integrate();
  publishCoordinates();
}

function schedule() {
  if (timer === null) {
    timer = setTimeout(tick, 1000 / 60);
  }
}

self.addEventListener("message", (event) => {
  const message = event.data;

  if (message.nodes) {
    nodesById.clear();
    nodes = message.nodes.map((input) => {
      const node = {
        id: input.id,
        x: input.x,
        y: input.y,
        vx: 0,
        vy: 0,
        fx: null,
        fy: null,
      };
      nodesById.set(node.id, node);
      return node;
    });
  }

  if (message.links) {
    rebuildLinks(message.links);
  }

  if (message.forces) {
    Object.assign(forces, message.forces);
  }

  if (message.forceNode) {
    const node = nodesById.get(message.forceNode.id);
    if (node) {
      node.fx = message.forceNode.x;
      node.fy = message.forceNode.y;
    }
  }

  if (message.alpha !== undefined) {
    alpha = Math.max(alpha, message.alpha);
  }

  if (message.alphaTarget !== undefined) {
    alphaTarget = message.alphaTarget;
  }

  if (message.run) {
    schedule();
  }
});
