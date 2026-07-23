import {
  Activity,
  Bot,
  Files,
  HelpCircle,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

interface RibbonProps {
  leftOpen: boolean;
  onToggleLeft: () => void;
  onToggleAsk: () => void;
  onOpenSettings: () => void;
}

interface RibbonButtonProps {
  label: string;
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
  testId?: string;
}

function RibbonButton({
  label,
  active = false,
  onClick,
  children,
  testId,
}: RibbonButtonProps) {
  return (
    <button
      className={`ribbon-button${active ? " is-active" : ""}`}
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      data-testid={testId}
    >
      {children}
    </button>
  );
}

export function Ribbon({
  leftOpen,
  onToggleLeft,
  onToggleAsk,
  onOpenSettings,
}: RibbonProps) {
  return (
    <nav className="app-ribbon" aria-label="应用工具栏">
      <div className="ribbon-main">
        <RibbonButton
          label={leftOpen ? "收起左侧栏" : "展开左侧栏"}
          onClick={onToggleLeft}
        >
          {leftOpen ? <PanelLeftClose /> : <PanelLeftOpen />}
        </RibbonButton>
        <RibbonButton label="文件" active>
          <Files />
        </RibbonButton>
        <RibbonButton label="搜索">
          <Search />
        </RibbonButton>
        <RibbonButton label="关系图" active>
          <Network />
        </RibbonButton>
        <RibbonButton label="打开问答" onClick={onToggleAsk}>
          <Sparkles />
        </RibbonButton>
        <RibbonButton label="模型状态">
          <Bot />
        </RibbonButton>
        <RibbonButton label="系统健康">
          <Activity />
        </RibbonButton>
      </div>

      <div className="ribbon-footer">
        <RibbonButton label="帮助">
          <HelpCircle />
        </RibbonButton>
        <RibbonButton
          label="设置"
          onClick={onOpenSettings}
          testId="model-settings-trigger"
        >
          <Settings />
        </RibbonButton>
      </div>
    </nav>
  );
}
