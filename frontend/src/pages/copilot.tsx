
import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { api } from '@/lib/api-client';
import {
  Card,
  CardContent,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import {
  Plus,
  Search,
  Upload,
  BarChart3,
  Lightbulb,
  Play,
  MoreHorizontal,
  PanelRightClose,
  PanelRightOpen,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  FileText,
  Download,
  Trash2,
  X,
  Loader2,
  Mic,
  Pencil,
  Pin,
  PinOff,
  Package,
  Copy,
  Quote,
  Share2,
  Bookmark,
  Camera,
  ChevronDown,
  Cpu,
  Rocket,
  ExternalLink,
  CheckCircle2,
  Siren,
  Activity,
  Archive,
  Server,
  FileSpreadsheet,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { demoSessions, type ChatSession } from '@/lib/demo-data';
import { useAuth } from '@/contexts/auth-context';
import { usePlatform } from '@/contexts/platform-context';
import { ModelSelector, DEFAULT_MODEL_CONFIG, type ModelConfig } from '@/components/model-selector';
// Note: Model selection is UI-only; actual LLM calls go through backend Agent API
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { MarkdownRenderer, StreamingMarkdown } from '@/components/markdown-renderer';
import { ThinkingBubble, type ThinkingStep } from '@/components/thinking-bubble';
import { NotificationCenter } from '@/components/notification-center';

/* ─── AI Robot Avatar SVG ─── */
/* ─── Robot Avatar Presets ─── */
const AVATAR_PRESETS = [
  { id: 'robot', label: '默认机器人', color: 'from-blue-500 via-indigo-500 to-violet-600', shadow: 'shadow-indigo-500/30', svg: 'robot' },
  { id: 'cat', label: '智能猫咪', color: 'from-amber-400 via-orange-500 to-rose-500', shadow: 'shadow-orange-500/30', svg: 'cat' },
  { id: 'owl', label: '智慧猫头鹰', color: 'from-emerald-500 via-teal-500 to-cyan-600', shadow: 'shadow-teal-500/30', svg: 'owl' },
  { id: 'bear', label: '可靠小熊', color: 'from-rose-400 via-pink-500 to-fuchsia-600', shadow: 'shadow-pink-500/30', svg: 'bear' },
  { id: 'fox', label: '灵动小狐狸', color: 'from-red-400 via-orange-500 to-amber-500', shadow: 'shadow-red-500/30', svg: 'fox' },
  { id: 'panda', label: '数据熊猫', color: 'from-gray-500 via-slate-600 to-zinc-700', shadow: 'shadow-slate-500/30', svg: 'panda' },
];

function AvatarSvg({ type, size }: { type: string; size: number }) {
  const s = size * 0.6;
  switch (type) {
    case 'cat':
      return (
        <svg width={s} height={s} viewBox="0 0 36 36" fill="none">
          <polygon points="8,12 4,2 14,8" fill="white" fillOpacity="0.9" />
          <polygon points="28,12 32,2 22,8" fill="white" fillOpacity="0.9" />
          <ellipse cx="18" cy="20" rx="12" ry="11" fill="white" fillOpacity="0.95" />
          <ellipse cx="13" cy="18" rx="2.5" ry="3" fill="#f97316" />
          <ellipse cx="23" cy="18" rx="2.5" ry="3" fill="#f97316" />
          <circle cx="14" cy="17" r="1" fill="white" />
          <circle cx="24" cy="17" r="1" fill="white" />
          <ellipse cx="18" cy="23" rx="1.5" ry="1" fill="#fb923c" />
          <line x1="6" y1="20" x2="1" y2="18" stroke="white" strokeWidth="1" strokeLinecap="round" />
          <line x1="6" y1="22" x2="1" y2="23" stroke="white" strokeWidth="1" strokeLinecap="round" />
          <line x1="30" y1="20" x2="35" y2="18" stroke="white" strokeWidth="1" strokeLinecap="round" />
          <line x1="30" y1="22" x2="35" y2="23" stroke="white" strokeWidth="1" strokeLinecap="round" />
        </svg>
      );
    case 'owl':
      return (
        <svg width={s} height={s} viewBox="0 0 36 36" fill="none">
          <ellipse cx="18" cy="22" rx="14" ry="12" fill="white" fillOpacity="0.95" />
          <polygon points="6,14 10,4 14,14" fill="white" fillOpacity="0.8" />
          <polygon points="22,14 26,4 30,14" fill="white" fillOpacity="0.8" />
          <circle cx="13" cy="20" r="5" fill="#0d9488" />
          <circle cx="23" cy="20" r="5" fill="#0d9488" />
          <circle cx="13" cy="20" r="3" fill="#fde68a" />
          <circle cx="23" cy="20" r="3" fill="#fde68a" />
          <circle cx="13" cy="20" r="1.5" fill="#0d9488" />
          <circle cx="23" cy="20" r="1.5" fill="#0d9488" />
          <path d="M16 26 L18 28 L20 26" stroke="#0d9488" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </svg>
      );
    case 'bear':
      return (
        <svg width={s} height={s} viewBox="0 0 36 36" fill="none">
          <circle cx="8" cy="10" r="5" fill="white" fillOpacity="0.8" />
          <circle cx="28" cy="10" r="5" fill="white" fillOpacity="0.8" />
          <circle cx="8" cy="10" r="3" fill="#f9a8d4" />
          <circle cx="28" cy="10" r="3" fill="#f9a8d4" />
          <ellipse cx="18" cy="22" rx="14" ry="12" fill="white" fillOpacity="0.95" />
          <ellipse cx="13" cy="18" rx="2" ry="2.5" fill="#1f2937" />
          <ellipse cx="23" cy="18" rx="2" ry="2.5" fill="#1f2937" />
          <circle cx="14" cy="17" r="0.8" fill="white" />
          <circle cx="24" cy="17" r="0.8" fill="white" />
          <ellipse cx="18" cy="24" rx="3" ry="2" fill="#f9a8d4" />
          <path d="M15 24 Q18 26 21 24" stroke="#1f2937" strokeWidth="1" fill="none" />
        </svg>
      );
    case 'fox':
      return (
        <svg width={s} height={s} viewBox="0 0 36 36" fill="none">
          <polygon points="6,16 2,4 14,10" fill="white" fillOpacity="0.9" />
          <polygon points="30,16 34,4 22,10" fill="white" fillOpacity="0.9" />
          <polygon points="6,16 4,8 12,12" fill="#fef3c7" />
          <polygon points="30,16 32,8 24,12" fill="#fef3c7" />
          <ellipse cx="18" cy="22" rx="13" ry="11" fill="white" fillOpacity="0.95" />
          <path d="M9 16 L18 12 L27 16 L25 26 L18 30 L11 26 Z" fill="#fef3c7" />
          <ellipse cx="14" cy="19" rx="1.8" ry="2.2" fill="#1f2937" />
          <ellipse cx="22" cy="19" rx="1.8" ry="2.2" fill="#1f2937" />
          <circle cx="14.8" cy="18.2" r="0.6" fill="white" />
          <circle cx="22.8" cy="18.2" r="0.6" fill="white" />
          <circle cx="18" cy="25" r="1.5" fill="#1f2937" />
        </svg>
      );
    case 'panda':
      return (
        <svg width={s} height={s} viewBox="0 0 36 36" fill="none">
          <circle cx="9" cy="10" r="5" fill="#e5e7eb" />
          <circle cx="27" cy="10" r="5" fill="#e5e7eb" />
          <ellipse cx="18" cy="22" rx="14" ry="12" fill="white" fillOpacity="0.95" />
          <ellipse cx="12" cy="18" rx="4" ry="3.5" fill="#1f2937" />
          <ellipse cx="24" cy="18" rx="4" ry="3.5" fill="#1f2937" />
          <circle cx="12" cy="18" r="1.5" fill="white" />
          <circle cx="24" cy="18" r="1.5" fill="white" />
          <ellipse cx="18" cy="25" rx="2.5" ry="1.5" fill="#1f2937" />
          <path d="M15 26 Q18 28 21 26" stroke="#1f2937" strokeWidth="1" fill="none" />
        </svg>
      );
    default: // robot
      return (
        <svg width={s} height={s} viewBox="0 0 36 36" fill="none">
          <line x1="18" y1="2" x2="18" y2="8" stroke="white" strokeWidth="2" strokeLinecap="round" />
          <circle cx="18" cy="2" r="2" fill="#fde68a" />
          <rect x="6" y="8" width="24" height="18" rx="6" fill="white" fillOpacity="0.95" />
          <circle cx="13" cy="17" r="3" fill="#6366f1">
            <animate attributeName="r" values="3;3.5;3" dur="2s" repeatCount="indefinite" />
          </circle>
          <circle cx="23" cy="17" r="3" fill="#6366f1">
            <animate attributeName="r" values="3;3.5;3" dur="2s" repeatCount="indefinite" />
          </circle>
          <circle cx="14" cy="16" r="1" fill="white" />
          <circle cx="24" cy="16" r="1" fill="white" />
          <path d="M13 23 Q18 26 23 23" stroke="#6366f1" strokeWidth="1.5" fill="none" strokeLinecap="round" />
          <rect x="2" y="13" width="4" height="8" rx="2" fill="white" fillOpacity="0.7" />
          <rect x="30" y="13" width="4" height="8" rx="2" fill="white" fillOpacity="0.7" />
        </svg>
      );
  }
}

function RobotAvatar({ size = 36, className = '', avatarId = 'robot', avatarUrl, onClick }: { size?: number; className?: string; avatarId?: string; avatarUrl?: string; onClick?: () => void }) {
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt="AI"
        className={`rounded-full object-cover shadow-md ${className} ${onClick ? 'cursor-pointer' : ''}`}
        style={{ width: size, height: size }}
        onClick={onClick}
        role={onClick ? 'button' : undefined}
      />
    );
  }
  const preset = AVATAR_PRESETS.find((p) => p.id === avatarId) || AVATAR_PRESETS[0];
  return (
    <div
      className={`flex items-center justify-center rounded-full bg-gradient-to-br ${preset.color} shadow-md ${preset.shadow} ${className} ${onClick ? 'cursor-pointer' : ''}`}
      style={{ width: size, height: size }}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
    >
      <AvatarSvg type={preset.svg} size={size} />
    </div>
  );
}

/* ─── User Avatar ─── */
function UserAvatar({ size = 32, name = '张', className = '' }: { size?: number; name?: string; className?: string }) {
  return (
    <div
      className={`flex items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-bold shadow-sm ${className}`}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
    >
      {name.charAt(0)}
    </div>
  );
}

/* ─── AI Assistant Settings ─── */
interface AssistantSettings {
  name: string;
  personality: string;
  customPrompt: string;
  avatarId: string;
  avatarUrl: string;
}

const DEFAULT_ASSISTANT: AssistantSettings = {
  name: 'FinForge 智能建模',
  personality: '专业严谨',
  customPrompt: '',
  avatarId: 'robot',
  avatarUrl: '',
};

const PERSONALITIES = [
  { value: '专业严谨', label: '专业严谨', desc: '标准金融建模顾问风格，用词精确、逻辑清晰' },
  { value: '亲切耐心', label: '亲切耐心', desc: '更友好、耐心解释概念，适合初学者' },
  { value: '简洁高效', label: '简洁高效', desc: '回复简短直接，聚焦核心结论' },
  { value: '教学引导', label: '教学引导', desc: '一步步引导思考，帮助理解原理' },
];

const quickActions = [
  { label: '上传数据', icon: Upload, keyword: '帮我上传金融交易数据' },
  { label: '开始数据分析', icon: BarChart3, keyword: '请对数据进行质量检查和分布分析' },
  { label: '特征工程建议', icon: Lightbulb, keyword: '请给我特征工程建议' },
  { label: '模型路线推荐', icon: BarChart3, keyword: '推荐适合的模型训练方案' },
  { label: '训练模型', icon: Play, keyword: '开始训练模型' },
  { label: '入库与部署', icon: MoreHorizontal, keyword: '将模型入库并部署上线' },
];



interface SessionCardProps {
  session: ChatSession;
  isActive: boolean;
  renamingId: string | null;
  renameValue: string;
  onSelect: () => void;
  onRename: () => void;
  onRenameValueChange: (v: string) => void;
  onRenameConfirm: () => void;
  onDelete: () => void;
  onPin: () => void;
}

function SessionCard({ session, isActive, renamingId, renameValue, onSelect, onRename, onRenameValueChange, onRenameConfirm, onDelete, onPin }: SessionCardProps) {
  const isRenaming = renamingId === session.id;

  return (
    <div
      className={`group relative rounded-lg px-2.5 py-2 transition-all duration-150 ${
        isActive
          ? 'bg-blue-50/80 shadow-sm'
          : 'hover:bg-accent/60'
      }`}
    >
      {isRenaming ? (
        <div className="flex items-center gap-1.5">
          <input
            autoFocus
            value={renameValue}
            onChange={(e) => onRenameValueChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onRenameConfirm();
              if (e.key === 'Escape') { onRenameValueChange(''); onRenameConfirm(); }
            }}
            onBlur={onRenameConfirm}
            className="h-6 flex-1 rounded border border-blue-300 bg-white px-2 text-sm outline-none focus:ring-1 focus:ring-blue-400"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      ) : (
        <div
          onClick={onSelect}
          className="w-full cursor-pointer"
        >
          <div className="flex items-center justify-between gap-1.5">
            <div className="flex min-w-0 items-center gap-1.5">
              {session.pinned && <Pin className="h-3 w-3 shrink-0 text-blue-500" />}
              <span className="truncate text-[13px] font-medium">{session.title}</span>
            </div>
            <div className="flex shrink-0 items-center">
              <span className="text-[11px] text-muted-foreground">{session.time}</span>
              <div
                className="ml-0.5 opacity-0 transition-opacity group-hover:opacity-100"
                onClick={(e) => e.stopPropagation()}
              >
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex h-5 w-5 items-center justify-center rounded hover:bg-accent">
                      <MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-40">
                    <DropdownMenuItem onClick={onRename} className="gap-2">
                      <Pencil className="h-3.5 w-3.5" /> 重命名话题
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={onPin} className="gap-2">
                      {session.pinned ? <PinOff className="h-3.5 w-3.5" /> : <Pin className="h-3.5 w-3.5" />}
                      {session.pinned ? '取消置顶' : '置顶话题'}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={onDelete} className="gap-2 text-red-600 focus:text-red-600">
                      <Trash2 className="h-3.5 w-3.5" /> 删除话题
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
          <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
            {session.status} · {session.progress}
          </div>
        </div>
      )}

    </div>
  );
}

export default function CopilotPage() {
  const { authHeaders: getAuthHeaders } = useAuth();
  const platform = usePlatform();
  const { tasks, addTask, updateTask } = platform;
  const STORAGE_KEY = 'finforge-copilot-sessions';
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>('');
  const [loadingSessions, setLoadingSessions] = useState(true);
  const currentSession = sessions.find((s) => s.id === currentSessionId) || sessions[0] || null;
  const hasRepoModel = useCallback((models: any[] = []) => (
    models.some((model) => Boolean(model?.inRepo || model?.repositoryName || model?.repository_name))
  ), []);
  const hasDeployedModel = useCallback((models: any[] = []) => (
    models.some((model) => (
      Boolean(model?.deployed)
      || Number(model?.runningServiceCount || 0) > 0
      || model?.status === 'deployed'
      || (Array.isArray(model?.serviceInstances) && model.serviceInstances.some((svc: any) => svc?.status === 'running'))
    ))
  ), []);
  const toBackendModels = useCallback((models: any[] = []) => {
    const namesWithRepo = new Set(
      models
        .filter((model) => Boolean(model?.inRepo || model?.repositoryName || model?.repository_name))
        .map((model) => String(model.modelName || model.name || '').toLowerCase())
    );
    const seen = new Set<string>();
    return models
      .filter((model) => {
        const name = String(model.modelName || model.name || `模型 ${model.modelId || model.modelVersionId || ''}`);
        const hasRepo = Boolean(model?.inRepo || model?.repositoryName || model?.repository_name);
        if (namesWithRepo.has(name.toLowerCase()) && !hasRepo) return false;
        const key = [name.toLowerCase(), String(model.version || '1.0.0'), String(model.repositoryName || model.repository_name || '').toLowerCase()].join('|');
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .map((m: any) => {
        const status: 'running' | 'stopped' | 'training' | 'deployed' =
          (m.deployed || Number(m.runningServiceCount || 0) > 0) ? 'deployed' :
          m.status === 'running' ? 'running' :
          m.status === 'training' ? 'training' :
          m.status === 'deployed' ? 'deployed' : 'stopped';
        return {
          name: String(m.modelName || m.name || `模型 ${m.modelId || m.modelVersionId || ''}`),
          version: String(m.version || '1.0.0'),
          status,
          time: String(m.time || ''),
        };
      });
  }, []);
  const workflowStepMap: Record<string, string> = { data_access: 'data', feature_engineering: 'feature', model_training: 'train', model_evaluation: 'eval' };
  const workflowOrder = ['data', 'feature', 'train', 'eval'];
  type WorkflowStepStatus = 'pending' | 'running' | 'completed';
  type WorkflowStep = {id: string; name: string; status: WorkflowStepStatus; duration?: string; output?: string; detail?: string};
  type WorkflowVersion = {version: string; steps: WorkflowStep[]; repoStatus: '未入库' | '已入库'; deployStatus: '未部署' | '已部署'; pipelineId?: string};
  const createEmptyWorkflowVersion = (): WorkflowVersion => ({
    version: '1.0v',
    steps: [
      { id: 'data', name: '数据接入', status: 'pending' },
      { id: 'feature', name: '特征工程', status: 'pending' },
      { id: 'train', name: '模型训练', status: 'pending' },
      { id: 'eval', name: '模型评估', status: 'pending' },
    ],
    repoStatus: '未入库',
    deployStatus: '未部署',
  });
  const workflowSessionRef = useRef<string>('');
  const workflowStatusRank: Record<WorkflowStepStatus, number> = { pending: 0, running: 1, completed: 2 };
  const keepWorkflowForward = (next: WorkflowStep, previous?: WorkflowStep): WorkflowStep => {
    if (!previous) return next;
    return workflowStatusRank[previous.status] > workflowStatusRank[next.status]
      ? { ...next, ...previous, name: next.name || previous.name }
      : next;
  };
  const mapBackendWorkflowSteps = (steps: any[], previous?: WorkflowStep[]) => {
    const previousById = new Map((previous || []).map((step) => [step.id, step]));
    return steps.map((step: any) => {
      const mapped: WorkflowStep = {
        id: workflowStepMap[step.id] || step.id,
        name: step.name,
        status: ['pending', 'running', 'completed'].includes(step.status) ? step.status : 'pending',
      };
      return keepWorkflowForward(mapped, previousById.get(mapped.id));
    });
  };
  const isDeploymentSuccessText = (text: string) => (
    text.includes('服务实例部署成功')
    || text.includes('部署成功')
    || text.includes('已部署')
    || /deploy(?:ed|ment)?\s+(?:success|succeeded|ready)/i.test(text)
  );

  useEffect(() => {
    if (!currentSessionId) return;
    workflowSessionRef.current = currentSessionId;
    setActiveVersionIdx(0);
    setWorkflowVersions([createEmptyWorkflowVersion()]);
  }, [currentSessionId]);

  // Load sessions from backend API
  useEffect(() => {
    const loadSessions = async () => {
      try {
        setLoadingSessions(true);
        const sessionsData = await api.sessions.list();
        const backendSessions = sessionsData?.items || [];
        
        // Convert backend session format to ChatSession format
        const converted: ChatSession[] = backendSessions.map((s: any) => {
          const sessionId = String(s.session_id || s.id || '');
          const createdAtRaw = String(s.createdAt || s.created_at || new Date().toISOString());
          const createdAt = new Date(createdAtRaw);
          const t = Number.isNaN(createdAt.getTime()) ? '--:--' : `${String(createdAt.getHours()).padStart(2, '0')}:${String(createdAt.getMinutes()).padStart(2, '0')}`;
          const messageCount = s.message_count || 0;
          
          let status: '待开始' | '进行中' | '已完成' = '待开始';
          let progress = '等待输入';
          if (messageCount === 0) {
            status = '待开始';
            progress = '等待输入';
          } else if (messageCount > 0 && messageCount < 5) {
            status = '进行中';
            progress = '建模中...';
          } else {
            status = '已完成';
            progress = '建模完成';
          }

          return {
            id: sessionId,
            title: String(s.title || s.project_name || '未命名会话'),
            status,
            progress,
            time: t,
            createdAt: createdAtRaw,
            messages: [],
            files: [],
            models: [],
            pinned: false,
            _rawSession: s,
          } as ChatSession & Record<string, unknown>;
        });

        setSessions(converted);
        
        // Set current session if not already set
        if (converted.length > 0 && !currentSessionId) {
          setCurrentSessionId(converted[0].id);
        }
      } catch (err) {
        console.error('Failed to load sessions from backend:', err);
        // Fallback to localStorage if backend fails
        if (typeof window !== 'undefined') {
          try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
              const parsed = JSON.parse(saved);
              if (Array.isArray(parsed) && parsed.length > 0) {
                setSessions(parsed);
                setCurrentSessionId(parsed[0].id);
              }
            }
          } catch {}
        }
      } finally {
        setLoadingSessions(false);
      }
    };

    loadSessions();
  }, []);

  // 如果没有会话，自动创建一个
  useEffect(() => {
    if (!loadingSessions && sessions.length === 0) {
      handleNewSession();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions.length, loadingSessions]);
  const [inputValue, setInputValue] = useState('');
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [leftPanelOpen, setLeftPanelOpen] = useState(true);

  // Auto-save sessions to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch {}
    }
  }, [sessions]);

  // Auto-name session after first user message
  const autoNameSession = useCallback((sessionId: string, userMessage: string) => {
    setSessions(prev => prev.map(s => {
      if (s.id !== sessionId || s.title !== '新建会话') return s;
      // Extract a meaningful title from the user's first message
      let title = userMessage.trim();
      // Remove common prefixes
      title = title.replace(/^(请|帮我|我需要|我想|开始|我要)\s*/,'');
      // Truncate to 20 chars
      if (title.length > 20) title = title.substring(0, 20) + '...';
      // Fallback
      if (!title) title = '新建会话';
      return { ...s, title };
    }));
  }, []);
  const [searchValue, setSearchValue] = useState('');
  const [fileCardVisible, setFileCardVisible] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<{ name: string; size: string; file: File }[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [quotedMessage, setQuotedMessage] = useState<{ content: string; role: string } | null>(null);
  const [quickCmdOpen, setQuickCmdOpen] = useState(false);
  const [fileSearch, setFileSearch] = useState('');
  const [modelSearch, setModelSearch] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingSessionId, setStreamingSessionId] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState('');
  const [chatSearchOpen, setChatSearchOpen] = useState(false);
  const [chatSearchQuery, setChatSearchQuery] = useState('');
  const [chatSearchTab, setChatSearchTab] = useState<'全部' | 'AI回复' | '我的消息'>('全部');
  const [modelConfig, setModelConfig] = useState<ModelConfig>(DEFAULT_MODEL_CONFIG);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastToolMetaRef = useRef<Array<{toolName: string; success: boolean; data: Record<string, unknown>}>>([]);
  const [pendingUploadSend, setPendingUploadSend] = useState<{
    sessionId: string;
    message: string;
    files: { name: string; size: string; type: string; id?: string }[];
  } | null>(null);

  // File upload helpers
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  const handleFilesSelected = useCallback(async (fileList: FileList | File[]) => {
    const validFiles = Array.from(fileList)
      .filter((f) => {
        const ext = f.name.split('.').pop()?.toLowerCase();
        return ['csv', 'xlsx', 'xls', 'parquet', 'json', 'txt'].includes(ext || '');
      });
    
    if (validFiles.length === 0) return;

    // 确保 session_id 有效 — 如果当前没有 session，先通过后端创建一个
    let sessionId = currentSessionId || currentSession?.id;
    if (!sessionId) {
      try {
        const created = await api.sessions.create('新建会话');
        sessionId = created.sessionId;
        // 前端本地也追加一条，保持 UI 一致
        const now = new Date();
        const t = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
        const newSession: ChatSession = {
          id: sessionId,
          title: '新建会话',
          status: '待开始',
          progress: '等待输入',
          time: t,
          createdAt: now.toISOString(),
          messages: [
            { role: 'ai', text: `你好！我是金融智能建模助手。\n\n我可以帮你完成从数据分析到模型部署的全流程建模。请上传数据文件开始建模。` },
          ],
        };
        setSessions(prev => [newSession, ...prev]);
        setCurrentSessionId(sessionId);
      } catch {
        // 后端创建失败，回退到本地 ID
        sessionId = `s${Date.now()}`;
        setCurrentSessionId(sessionId);
      }
    }

    // 真实上传到后端API
    let uploadSuccessCount = 0;
    const uploadedFiles: { name: string; size: string; type: string; id?: string }[] = [];
    for (const file of validFiles) {
      try {
        const data = await api.files.upload(sessionId, file);

        if (data) {
          uploadSuccessCount++;
          if (data.fileId) {
            uploadedFiles.push({
              id: String(data.fileId),
              name: data.fileName || file.name,
              size: formatFileSize(file.size),
              type: file.name.split('.').pop()?.toLowerCase() || 'file',
            });
          }
          // 上传成功，使用后端返回的真实数据
          const fileData = data;
          const sid = sessionId; // 捕获闭包变量
          setSessions((prev) =>
            prev.map((s) =>
              s.id === sid
                ? {
                    ...s,
                    files: [
                      ...(s.files || []),
                      {
                        id: fileData.fileId,
                        name: fileData.fileName || file.name,
                        size: String(fileData.fileSize || 0),
                        type: 'input' as const,
                        time: new Date().toLocaleString('zh-CN'),
                      },
                    ],
                  }
                : s
            )
          );
        } else {
          console.error('文件上传后端返回错误:', data);
        }
      } catch (e) {
        console.error('文件上传失败:', e);
      }
    }

    // 只有上传成功才继续发送消息
    if (uploadSuccessCount === 0) {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId
            ? {
                ...s,
                messages: [
                  ...s.messages,
                  { role: 'ai' as const, text: '❌ 文件上传失败，请检查网络连接或后端服务是否正常运行后重试。' },
                ],
              }
            : s
        )
      );
      return;
    }

    setFileCardVisible(true);

    // 上传完成后自动发送消息触发建模流程，附带文件信息
    const fileNames = validFiles.map(f => f.name).join('、');
    const autoMessage = `我已上传了数据文件：${fileNames}`;
    setCurrentSessionId(sessionId);
    setPendingUploadSend({ sessionId, message: autoMessage, files: uploadedFiles });
  }, [currentSessionId, currentSession?.id]);

  const removeAttachedFile = useCallback((index: number) => {
    const fileName = attachedFiles[index]?.name;
    const sid = currentSessionId;
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
    // 同步删除会话中的文件
    if (fileName) {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sid
            ? { ...s, files: (s.files || []).filter((f) => f.name !== fileName) }
            : s
        )
      );
    }
  }, [attachedFiles, currentSessionId]);

  const clearAttachedFiles = useCallback(() => {
    const fileNames = attachedFiles.map((f) => f.name);
    const sid = currentSessionId;
    setAttachedFiles([]);
    setFileCardVisible(false);
    // 同步清空会话中的文件
    setSessions((prev) =>
      prev.map((s) =>
        s.id === sid
          ? { ...s, files: (s.files || []).filter((f) => !fileNames.includes(f.name)) }
          : s
      )
    );
  }, [attachedFiles, currentSessionId]);

  // Drag & drop handlers for the entire chat area
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set to false if we're leaving the chat area entirely
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
      setIsDragOver(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files);
    }
  }, [handleFilesSelected]);

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [assistantSettings, setAssistantSettings] = useState<AssistantSettings>(DEFAULT_ASSISTANT);
  const [showAssistantSettings, setShowAssistantSettings] = useState(false);
  const [tempAssistantSettings, setTempAssistantSettings] = useState<AssistantSettings>(DEFAULT_ASSISTANT);
  const [sessionArtifacts, setSessionArtifacts] = useState<Record<string, { modelItems: any[]; allItems: any[] }>>({});

  const [userInfo] = useState({ name: '张三', initial: '张' });

  // Drift alert from Service page (URL param: ?alert=drift&precision=0.82)
  const [driftAlert, setDriftAlert] = useState(false);
  const [precisionClimb, setPrecisionClimb] = useState(0.82);
  const [precisionClimbDone, setPrecisionClimbDone] = useState(false);

  // Check drift alert on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('alert') === 'drift') {
      setDriftAlert(true);
      // Auto-dismiss drift alert banner after 8s
      const timer = setTimeout(() => setDriftAlert(false), 8000);
      return () => clearTimeout(timer);
    }
  }, []);

  // Precision climb animation when drift is triggered
  useEffect(() => {
    if (!driftAlert) return;
    const start = 0.82;
    const end = 0.962;
    const startedAt = performance.now();

    function animate(now: number) {
      const progress = Math.min((now - startedAt) / 2000, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setPrecisionClimb(start + (end - start) * eased);
      if (progress < 1) {
        window.requestAnimationFrame(animate);
      } else {
        setPrecisionClimbDone(true);
      }
    }

    const raf = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(raf);
  }, [driftAlert]);

  // Chat search results
  const chatSearchResults = useMemo(() => {
    if (!chatSearchQuery.trim() || !currentSession) return [];
    const q = chatSearchQuery.toLowerCase();
    return currentSession?.messages.filter(msg => {
      if (chatSearchTab === 'AI回复' && msg.role !== 'ai') return false;
      if (chatSearchTab === '我的消息' && msg.role !== 'user') return false;
      return msg.text.toLowerCase().includes(q);
    });
  }, [chatSearchQuery, chatSearchTab, currentSession]);

  const highlightMatch = (text: string, query: string) => {
    if (!query.trim()) return text;
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i} className="bg-yellow-200 rounded px-0.5">{part}</mark> : part
    );
  };

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      if (Number.isNaN(d.getTime())) return '';
      return `${d.getMonth()+1}月${d.getDate()}日 ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    } catch { return ''; }
  };

  const formatSessionCreatedAt = (value?: string) => {
    if (!value) return '创建时间未知';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '创建时间未知';
    return `创建于 ${d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })} ${d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`;
  };

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // 页面加载时从后端获取当前会话的文件列表和历史消息
  useEffect(() => {
    const loadSessionData = async () => {
      if (!currentSessionId) return;
      try {
        const [fileResult, historyResult, modelResult, workflowResult, outputResult] = await Promise.allSettled([
          api.sessions.files(currentSessionId),
          api.sessions.history(currentSessionId),
          api.sessions.models(currentSessionId),
          api.sessions.workflow(currentSessionId),
          api.sessions.modelOutputs(currentSessionId),
        ]);
        if (workflowSessionRef.current !== currentSessionId) return;

        const fileList = fileResult.status === 'fulfilled' ? (fileResult.value?.items || []) : [];
        const backendFiles = fileList.map((f: any) => ({
          id: f.fileId,
          name: f.fileName,
          size: formatFileSize(Number(f.fileSize || 0)),
          sizeBytes: Number(f.fileSize || 0),
          rows: Number(f.rows || 0),
          columnsCount: Number(f.columnsCount || 0),
          columns: Array.isArray(f.columns) ? f.columns : [],
          type: 'input' as const,
          time: f.uploadTime || new Date().toLocaleString('zh-CN'),
        }));

        const historyData = historyResult.status === 'fulfilled' ? historyResult.value : { items: [] };
        const historyMessages = historyData?.items || historyData || [];
        const messages = historyMessages.map((msg: any) => ({
          role: msg.role === 'user' ? 'user' : 'ai',
          text: String(msg.content || msg.text || ''),
          timestamp: msg.created_at || msg.time || new Date().toISOString(),
        }));

        const sessionModels = modelResult.status === 'fulfilled' ? (modelResult.value?.items || []) : [];
        const backendModels = toBackendModels(sessionModels);

        const workflow = workflowResult.status === 'fulfilled' ? workflowResult.value : null;
        if (workflow?.steps?.length) {
          const deployed = hasDeployedModel(sessionModels);
          setWorkflowVersions(prev => [{
            version: '1.0v',
            repoStatus: hasRepoModel(sessionModels) ? '已入库' : '未入库',
            deployStatus: deployed ? '已部署' : (workflowSessionRef.current === currentSessionId ? (prev[0]?.deployStatus || '未部署') : '未部署'),
            steps: mapBackendWorkflowSteps(
              workflow.steps,
              workflowSessionRef.current === currentSessionId ? prev[0]?.steps : undefined,
            ),
          }]);
        }

        if (outputResult.status === 'fulfilled') {
          setSessionArtifacts(prev => ({
            ...prev,
            [currentSessionId]: {
              modelItems: outputResult.value?.modelItems || [],
              allItems: (outputResult.value as any)?.allItems || [],
            },
          }));
        }

        setSessions(prev => prev.map(s => 
          s.id === currentSessionId 
            ? { ...s, files: backendFiles, messages, models: backendModels }
            : s
        ));
      } catch (e) {
        console.error('Failed to load session data:', e);
      }
    };
    loadSessionData();
  }, [currentSessionId, hasDeployedModel, hasRepoModel, toBackendModels]);

  // 加载会话绑定的模型
  useEffect(() => {
    if (!currentSessionId) return;
    (async () => {
      try {
        const modelsData = await api.sessions.models(currentSessionId);
        const sessionModels = modelsData?.items || [];
        const backendModels = toBackendModels(sessionModels);
        setSessions(prev => prev.map(s =>
          s.id === currentSessionId ? { ...s, models: backendModels } : s
        ));
        if (hasDeployedModel(sessionModels)) {
          setWorkflowVersions(prev => prev.map((version, idx) => idx !== 0 ? version : {
            ...version,
            deployStatus: '已部署' as const,
          }));
        }
      } catch { /* ignore */ }
    })();
  }, [currentSessionId, hasDeployedModel, toBackendModels]);

  // 页面加载时从后端恢复当前会话的工作流状态（解决刷新后工作数据流重置问题）
  useEffect(() => {
    const restoreWorkflowState = async () => {
      if (!currentSessionId) return;
      return;
      try {
        const pipelineData = await api.pipelines.list({ page: 1, pageSize: 20 });
        const pipelines: any[] = pipelineData?.items || [];
        if (pipelines.length === 0) return;

        const stepIdxToId: Record<number, string> = { 1: 'data', 2: 'feature', 3: 'train', 4: 'eval' };
        const stepNames: Record<string, string> = { data: '数据接入', feature: '特征工程', train: '模型训练', eval: '模型评估' };
        const stepOrder = ['data', 'feature', 'train', 'eval'];

        const restoredVersions = pipelines.map((pipeline: any, idx: number) => {
          const stepIndex = pipeline.currentStep ? stepOrder.indexOf(pipeline.currentStep) + 1 : (pipeline.step_index || 0);
          const pipelineStatus = pipeline.status || 'pending';
          const isConfirmed = pipelineStatus === 'confirmed';
          const isCompleted = pipelineStatus === 'completed' || isConfirmed;

          const steps = stepOrder.map((stepId, i) => {
            const stepNum = i + 1; // 1-based
            if (stepNum < stepIndex) {
              return { id: stepId, name: stepNames[stepId], status: 'completed' as const, output: `已完成${stepNames[stepId]}` };
            } else if (stepNum === stepIndex) {
              // 当前步骤：如果pipeline已confirmed/completed且这是最后一步，标记completed
              if (isCompleted && stepNum === 4) {
                return { id: stepId, name: stepNames[stepId], status: 'completed' as const, output: `已完成${stepNames[stepId]}` };
              }
              return { id: stepId, name: stepNames[stepId], status: 'completed' as const, output: `已完成${stepNames[stepId]}` };
            } else if (stepNum === stepIndex + 1 && (pipelineStatus === 'running')) {
              return { id: stepId, name: stepNames[stepId], status: 'running' as const, detail: `正在执行${stepNames[stepId]}...` };
            }
            return { id: stepId, name: stepNames[stepId], status: 'pending' as const };
          });

          return {
            version: `${idx + 1}.0v`,
            steps,
            repoStatus: isConfirmed ? '已入库' as const : '未入库' as const,
            deployStatus: '未部署' as const,
            pipelineId: pipeline.id || pipeline.pipeline_id,
          };
        });

        if (restoredVersions.length > 0) {
          setWorkflowVersions(restoredVersions);
          setActiveVersionIdx(0);
          prevVersionCountRef.current = restoredVersions.length;

          // 同时恢复轮询集合（对仍running的pipeline继续轮询）
          const runningIds = pipelines
            .filter((p: any) => p.status === 'running' || p.status === 'pending')
            .map((p: any) => p.id || p.pipeline_id)
            .filter(Boolean);
          if (runningIds.length > 0) {
            setPollingPipelineIds(new Set(runningIds));
          }

          // 恢复pipelineStatusMap
          const statusMap: Record<string, any> = {};
          pipelines.forEach((p: any) => {
            const pid = p.id || p.pipeline_id;
            if (pid) statusMap[pid] = p;
          });
          setPipelineStatusMap(statusMap);
        }
      } catch (e) {
        console.error('Failed to restore workflow state:', e);
      }
    };
    restoreWorkflowState();
  }, [currentSessionId, toBackendModels]);

  // 流水线状态轮询：检测消息中的流水线ID并自动更新状态
  const [pollingPipelineIds, setPollingPipelineIds] = useState<Set<string>>(new Set());
  const [pipelineStatusMap, setPipelineStatusMap] = useState<Record<string, any>>({});

  useEffect(() => {
    if (pollingPipelineIds.size === 0) return;
    const interval = setInterval(async () => {
      const stillRunning = new Set<string>();
      for (const pid of pollingPipelineIds) {
        try {
          const pipeline = await api.pipelines.get(pid);
          if (pipeline) {
            const prevPipeline = pipelineStatusMap[pid];
            setPipelineStatusMap(prev => ({ ...prev, [pid]: pipeline }));
            // Update workflow version from pipeline step_index
            const stepOrder = ['data', 'feature', 'train', 'eval'];
            const completedStepNum = pipeline.currentStep ? stepOrder.indexOf(pipeline.currentStep as string) + 1 : ((pipeline as any).step_index || 0) as number;
            if (completedStepNum > 0) {
              const stepIdxToId: Record<number, string> = { 1: 'data', 2: 'feature', 3: 'train', 4: 'eval' };
              setWorkflowVersions(prev => {
                const vIdx = prev.findIndex(v => v.pipelineId === pid);
                if (vIdx === -1) return prev;
                const versions = [...prev];
                const stepId = stepIdxToId[completedStepNum];
                versions[vIdx] = {
                  ...versions[vIdx],
                  steps: versions[vIdx].steps.map((s, i) => {
                    const stepPos = stepOrder.indexOf(s.id);
                    if (stepPos < completedStepNum - 1) return s.status !== 'completed' ? { ...s, status: 'completed' as const, output: `已完成${s.name}`, detail: undefined } : s;
                    if (stepPos === completedStepNum - 1) return { ...s, status: 'completed' as const, output: `已完成${s.name}`, detail: undefined };
                    return s;
                  }),
                };
                return versions;
              });
            }
            if (pipeline.status === 'confirmed') {
              setWorkflowVersions(prev => {
                const vIdx = prev.findIndex(v => v.pipelineId === pid);
                if (vIdx === -1) return prev;
                const versions = [...prev];
                versions[vIdx] = { ...versions[vIdx], repoStatus: '已入库' };
                return versions;
              });
            }
            if (pipeline.status === 'running' || pipeline.status === 'pending') {
              stillRunning.add(pid);
            }
            // 流水线刚完成时自动提示用户确认入库
            if (pipeline.status === 'completed' && (!prevPipeline || prevPipeline.status !== 'completed')) {
              const resultMsg = (pipeline as any).result_message || '';
              const modelId = (pipeline as any).model_id;
              const confirmMsg = `🎯 建模完成！${resultMsg}\n\n请回复"确认入库"将模型存入模型仓库，模型将可用于线上推理服务。`;
              setSessions(prev => prev.map(s => {
                if (s.id !== currentSessionId) return s;
                return {
                  ...s,
                  messages: [...s.messages, {
                    id: `pipeline-complete-${pid}-${Date.now()}`,
                    role: 'ai' as const,
                    text: confirmMsg,
                    timestamp: new Date().toLocaleTimeString(),
                  }],
                };
              }));
            }
          }
        } catch (e) {
          stillRunning.add(pid);
        }
      }
      if (stillRunning.size !== pollingPipelineIds.size) {
        setPollingPipelineIds(stillRunning);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [pollingPipelineIds]);

  useEffect(() => {
    if (streamingSessionId === currentSessionId) {
      scrollToBottom();
    }
  }, [currentSession?.messages, streamingText, scrollToBottom, streamingSessionId, currentSessionId]);

  // 切换回页面或切换会话时自动滚到底部
  useEffect(() => {
    scrollToBottom();
  }, [currentSessionId, toBackendModels]); // eslint-disable-line react-hooks/exhaustive-deps

  const generateThinkingSteps = (input: string): ThinkingStep[] => {
    const lower = input.toLowerCase();
    const steps: ThinkingStep[] = [];
    if (lower.includes('数据') || lower.includes('特征') || lower.includes('上传') || lower.includes('接入')) {
      steps.push({ label: '分析数据源结构', detail: '识别 CSV 字段类型、统计缺失值比例、检测异常值分布' });
      steps.push({ label: '评估特征质量', detail: '计算 IV 值、相关性矩阵、特征覆盖率，筛选高信息量特征' });
    }
    if (lower.includes('模型') || lower.includes('训练') || lower.includes('建模') || lower.includes('算法')) {
      steps.push({ label: '匹配算法方案', detail: '根据场景类型(二分类/回归)和样本量，从算法库筛选候选模型' });
      steps.push({ label: '设计调参策略', detail: '基于贝叶斯优化制定超参搜索空间和评估指标' });
    }
    if (lower.includes('评估') || lower.includes('指标') || lower.includes('ks') || lower.includes('auc') || lower.includes('roc')) {
      steps.push({ label: '计算评估指标', detail: 'KS/AUC/Gini/PSI 多维度交叉验证，生成模型评估报告' });
      steps.push({ label: '对比基线表现', detail: '与历史版本和随机基线对比，评估模型增益效果' });
    }
    if (lower.includes('部署') || lower.includes('服务') || lower.includes('上线') || lower.includes('推理')) {
      steps.push({ label: '检查部署条件', detail: '验证模型文件完整性、审批状态、服务端口可用性' });
      steps.push({ label: '配置服务参数', detail: '设定弹性扩缩容策略、A/B 流量分配、监控告警阈值' });
    }
    // Default steps for general queries
    if (steps.length === 0) {
      steps.push({ label: '理解建模需求', detail: '分析用户意图，确定建模场景和目标变量' });
      steps.push({ label: '检索知识库', detail: '匹配金融建模最佳实践和历史建模案例' });
    }
    return steps;
  };


  const syncTaskFromModelingResult = useCallback((sessionId: string, finalText: string) => {
    const success = /(建模完成|训练成功|模型训练成功|best_model\.(joblib|pkl))/i.test(finalText);
    if (!success) return;

    const session = sessions.find((s) => s.id === sessionId);
    const now = new Date().toISOString();
    const taskId = `task-${sessionId}`;
    const taskName = session?.title?.trim() && session.title.trim() !== '新建会话'
      ? session.title.trim()
      : `自动建模任务-${sessionId.slice(-6)}`;

    const modelPathMatch = finalText.match(/([\w./-]+best_model\.(?:joblib|pkl))/i);
    const predictionPathMatch = finalText.match(/([\w./-]+validation_predictions\.csv)/i);
    const dataFiles = (session?.files || [])
      .filter((f) => f.type === 'input')
      .map((f, idx) => ({
        id: `data-${sessionId}-${idx}`,
        name: f.name,
        type: 'data' as const,
        size: String(f.size),
        time: f.time || now,
        createdAt: f.time || now,
      }));
    const modelFiles = [
      modelPathMatch ? {
        id: `model-${sessionId}`,
        name: modelPathMatch[1].split('/').pop() || 'best_model.joblib',
        type: 'model' as const,
        size: '--',
        time: now,
        createdAt: now,
      } : null,
      predictionPathMatch ? {
        id: `pred-${sessionId}`,
        name: predictionPathMatch[1].split('/').pop() || 'validation_predictions.csv',
        type: 'report' as const,
        size: '--',
        time: now,
        createdAt: now,
      } : null,
    ].filter(Boolean);

    const existingTask = tasks.find((t) => t.id === taskId || t.sessionId === sessionId);
    const description = finalText.split('\n').find((line) => line.trim())?.slice(0, 120) || '通过 Copilot 自动完成建模训练';

    if (existingTask) {
      updateTask(existingTask.id, {
        name: taskName,
        status: 'completed',
        updatedAt: now,
        description,
        dataFiles,
        modelFiles: modelFiles as typeof existingTask.modelFiles,
        inRepo: existingTask.inRepo,
      });
      return;
    }

    addTask({
      id: taskId,
      name: taskName,
      status: 'completed',
      sessionId,
      createdAt: session?.createdAt || now,
      updatedAt: now,
      description,
      dataFiles,
      modelFiles: modelFiles as never[],
      codeFiles: [],
      inRepo: false,
    });
  }, [sessions, tasks, addTask, updateTask]);

  const updateWorkflowByUserIntent = useCallback((sessionId: string, message: string, hasNewFiles: boolean) => {
    const trimmed = message.trim();
    const normalized = trimmed.toLowerCase();
    const session = sessions.find((item) => item.id === sessionId);
    const lastAiText = [...(session?.messages || [])].reverse().find((item) => item.role === 'ai')?.text || '';
    const hasAny = (source: string, needles: string[]) => needles.some((needle) => source.includes(needle));
    const affirmative = hasAny(trimmed, ['同意', '确认', '是', '对', '可以', '开始', '好', '好的', '没错', '正确', '行', '继续']);
    const labelPrompt = hasAny(lastAiText, ['目标列', '标签列']);
    const configPrompt = hasAny(lastAiText, ['默认配置', '默认建模配置', '建模配置', '按以上配置', '开始建模', '进行建模', '测试集比例', '模型类型']);
    const trainingIntent = hasAny(trimmed, ['开始建模', '进行建模', '执行建模', '开始训练', '训练模型', '开始', '同意', '确认'])
      || hasAny(normalized, ['train', 'start', 'go']);
    let targetStep: 'data' | 'feature' | 'train' | null = null;

    if (hasNewFiles) {
      targetStep = 'data';
    } else if ((trainingIntent || affirmative) && configPrompt) {
      targetStep = 'train';
    } else if (affirmative && labelPrompt) {
      targetStep = 'feature';
    } else if (hasAny(trimmed, ['开始建模', '进行建模', '执行建模', '开始训练', '训练模型'])) {
      targetStep = 'train';
    }

    if (!targetStep) return;

    setWorkflowVersions(prev => prev.map((version, idx) => idx !== 0 ? version : {
      ...version,
      steps: version.steps.map((step) => {
        const stepPos = workflowOrder.indexOf(step.id);
        const targetPos = workflowOrder.indexOf(targetStep);
        if (stepPos < targetPos) return { ...step, status: 'completed' as const, detail: undefined, output: `已完成${step.name}` };
        if (stepPos === targetPos) return { ...step, status: 'running' as const, detail: `正在执行${step.name}...`, output: undefined };
        return { ...step, status: 'pending' as const, detail: undefined, output: undefined };
      }),
    }));
  }, [sessions]);

  const handleSend = async (overrideMessage?: string, _unused?: unknown, msgFiles?: { name: string; size: string; type: string; id?: number | string; time?: string }[]) => {
    if ((!inputValue.trim() && attachedFiles.length === 0 && !overrideMessage) || isStreaming) return;
    const userMsg = overrideMessage || inputValue.trim();
    const sessionId = currentSessionId;
    const quoteForApi = quotedMessage;
    const filesToSend = [...attachedFiles];
    setInputValue('');
    setQuotedMessage(null);
    clearAttachedFiles();

    // Build display text with file info
    const fileNames = filesToSend.map((f) => f.name).join(', ');
    const displayText = fileNames ? `[附件: ${fileNames}]${userMsg ? '\n' + userMsg : ''}` : userMsg;

    // 文件信息（用于渲染文件卡片）
    const messageFiles: { name: string; size: string; type: string; id?: number | string; time?: string }[] = msgFiles || filesToSend.map(f => ({
      name: f.name,
      size: f.size,
      type: f.name.split('.').pop()?.toLowerCase() || 'file',
    }));
    let fileIds = (messageFiles || []).map((f) => f.id).filter(Boolean).map((id) => String(id));

    // Add user message
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          status: '处理中',
          progress: 'AI 正在思考',
          _streamingText: undefined,
          messages: [...s.messages, { role: 'user' as const, text: displayText, timestamp: new Date().toISOString(), files: messageFiles.length > 0 ? messageFiles : undefined }],
        };
      })
    );
    updateWorkflowByUserIntent(sessionId, userMsg, messageFiles.length > 0);

    // Auto-name the session based on first real user message
    autoNameSession(sessionId, userMsg);

    setIsStreaming(true);
    setStreamingSessionId(sessionId);
    setStreamingText('');

    // Generate thinking steps based on user input
    const thinkingSteps: string[] = [];
    const lowerMsg = userMsg.toLowerCase();
    if (lowerMsg.includes('数据') || lowerMsg.includes('上传') || lowerMsg.includes('csv') || lowerMsg.includes('接入')) {
      thinkingSteps.push('分析用户的数据接入需求...', '评估数据源格式与质量要求', '规划数据清洗与预处理流程');
    } else if (lowerMsg.includes('特征') || lowerMsg.includes('工程') || lowerMsg.includes('选择') || lowerMsg.includes('iv') || lowerMsg.includes('重要性')) {
      thinkingSteps.push('回顾已有特征工程方案...', '计算特征IV值与相关性矩阵', '筛选高区分度特征组合');
    } else if (lowerMsg.includes('训练') || lowerMsg.includes('模型') || lowerMsg.includes('算法') || lowerMsg.includes('调参')) {
      thinkingSteps.push('分析建模目标与数据特征...', '匹配最优算法族（LR/XGBoost/GBDT）', '设计超参搜索空间与交叉验证策略');
    } else if (lowerMsg.includes('评估') || lowerMsg.includes('ks') || lowerMsg.includes('auc') || lowerMsg.includes('roc') || lowerMsg.includes('指标')) {
      thinkingSteps.push('加载模型评估报告...', '计算KS/AUC/PSI等金融风控指标', '对比不同阈值下的业务收益');
    } else if (lowerMsg.includes('部署') || lowerMsg.includes('服务') || lowerMsg.includes('上线') || lowerMsg.includes('推理')) {
      thinkingSteps.push('检查模型产物与部署依赖...', '评估服务资源配置与弹性策略', '规划灰度发布与监控方案');
    } else {
      thinkingSteps.push('理解用户意图与业务上下文...', '检索相关建模知识与最佳实践', '规划最优响应策略');
    }
    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      // Build message history for the API — use the captured sessionId
      const sessionForApi = sessions.find((s) => s.id === sessionId);
      const apiMessages = (sessionForApi?.messages || [])
        .filter((m) => m.role === 'user' || m.role === 'ai')
        .map((m) => ({
          role: m.role === 'user' ? 'user' as const : 'assistant' as const,
          content: m.text,
        }));
      apiMessages.push({ role: 'user', content: quoteForApi ? `[引用] "${quoteForApi.content.slice(0, 80)}${quoteForApi.content.length > 80 ? '...' : ''}"\n\n${displayText}` : displayText });

      const requestId = `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      let fullText = '';
      lastToolMetaRef.current = [];

      const thinkingForMsg = generateThinkingSteps(userMsg);
      const thinkingDuration = (thinkingForMsg.length * 1.2).toFixed(1) + 's';

      setSessions(prev => prev.map(s => {
        if (s.id !== sessionId) return s;
        return { ...s, _thinking: { steps: thinkingForMsg, duration: thinkingDuration } };
      }));

      await new Promise<void>((resolve, reject) => {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${protocol}://${window.location.host}/api/sessions/${encodeURIComponent(sessionId)}/message/ws`);
        let settled = false;
        
        let timeoutId: number | null = null;
        const resetTimeout = () => {
          if (timeoutId !== null) window.clearTimeout(timeoutId);
          timeoutId = window.setTimeout(() => finish(new Error('WebSocket 对话超时')), 1000 * 60 * 30);
        };
        
        const finish = (err?: Error) => {
          if (settled) return;
          settled = true;
          if (timeoutId !== null) window.clearTimeout(timeoutId);
          try { ws.close(); } catch {}
          if (err) reject(err);
          else resolve();
        };
        
        resetTimeout(); // 初始化超时
        
        ws.onopen = () => {
          ws.send(JSON.stringify({
            requestId,
            message: quoteForApi ? `[引用] "${quoteForApi.content.slice(0, 80)}${quoteForApi.content.length > 80 ? '...' : ''}"\n\n${displayText}` : displayText,
            file_ids: fileIds.length > 0 ? fileIds : undefined,
            stream: true,
          }));
        };
        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            if (payload.requestId && payload.requestId !== requestId) return;
            
            resetTimeout(); // 每次收到消息都重置超时计时器
            
            const eventName = payload.event;
            const data = payload.data || {};
            
            if (eventName === 'ping') {
              // 收到心跳，回复 pong
              try {
                ws.send(JSON.stringify({ event: 'pong', requestId, data: { timestamp: Date.now() } }));
              } catch {}
              return;
            }
            
            if (eventName === 'message' && data.delta) {
              fullText += String(data.delta);
              setStreamingText(fullText);
              setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, _streamingText: fullText, _thinking: { steps: thinkingForMsg, duration: thinkingDuration } } : s));
            } else if (eventName === 'final' && data.message) {
              fullText = String(data.message);
              setStreamingText(fullText);
              setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, _streamingText: fullText, _thinking: { steps: thinkingForMsg, duration: thinkingDuration } } : s));
            } else if (eventName === 'workflow' && data.workflow_state) {
              const stateToStep: Record<string, string> = { data_access: 'data', feature_engineering: 'feature', model_training: 'train', model_evaluation: 'eval', completed: 'eval' };
              const currentStep = stateToStep[String(data.workflow_state)];
              if (currentStep) {
                const order = ['data', 'feature', 'train', 'eval'];
                const isRunningEvent = String(data.status || '').toLowerCase() === 'running';
                const isCompletedWorkflow = String(data.workflow_state) === 'completed';
                setWorkflowVersions(prev => prev.map((version, idx) => idx !== activeVersionIdx ? version : {
                  ...version,
                  steps: version.steps.map((step) => {
                    const stepPos = order.indexOf(step.id);
                    const currentPos = order.indexOf(currentStep);
                    if (isCompletedWorkflow || stepPos < currentPos || (!isRunningEvent && stepPos === currentPos)) {
                      return keepWorkflowForward({ ...step, status: 'completed' as const, detail: undefined, output: `已完成${step.name}` }, step);
                    }
                    if (isRunningEvent && stepPos === currentPos) {
                      return keepWorkflowForward({ ...step, status: 'running' as const, detail: `正在执行${step.name}...`, output: undefined }, step);
                    }
                    return step;
                  }),
                }));
              }
            } else if (eventName === 'tool_results' && Array.isArray(data.tools)) {
              processToolResults(data.tools as Array<{toolName: string; success: boolean; data: Record<string, unknown>}>);
              lastToolMetaRef.current = data.tools as Array<{toolName: string; success: boolean; data: Record<string, unknown>}>;
              if ((data.tools as Array<{toolName: string; success: boolean; data: Record<string, unknown>}>).some((tool) => tool.success && /deploy|service|instance|部署|服务/i.test(tool.toolName))) {
                setWorkflowVersions(prev => prev.map((version, idx) => idx !== activeVersionIdx ? version : { ...version, deployStatus: '已部署' as const }));
              }
            } else if (eventName === 'error') {
              fullText += `\n\n⚠️ 错误: ${data.message || 'WebSocket 对话失败'}`;
            } else if (eventName === 'done') {
              finish();
            }
          } catch (err) {
            console.warn('WebSocket message parse failed:', err);
          }
        };
        ws.onerror = () => {
          finish(new Error('WebSocket 连接失败'));
        };
        ws.onclose = () => {
          if (!settled) finish();
        };
        abortController.signal.addEventListener('abort', () => {
          finish(new DOMException('Aborted', 'AbortError') as unknown as Error);
        }, { once: true });
      });

      // Finalize: add AI message to session
      const finalText = fullText || '抱歉，未能获取响应，请重试。';
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== sessionId) return s;
          return {
            ...s,
            status: 'AI 已回复',
            progress: '等待下一步指令',
            _streamingText: undefined,
            messages: [...s.messages, { role: 'ai' as const, text: finalText, timestamp: new Date().toISOString(), thinking: { steps: thinkingForMsg, duration: thinkingDuration }, toolMeta: lastToolMetaRef.current }],
          };
        })
      );

      // 检测流水线ID并启动轮询
      syncTaskFromModelingResult(sessionId, finalText);
      if (isDeploymentSuccessText(finalText)) {
        setWorkflowVersions(prev => prev.map((version, idx) => idx !== activeVersionIdx ? version : {
          ...version,
          deployStatus: '已部署' as const,
        }));
      }
      try {
        const [workflow, outputs, models] = await Promise.all([
          api.sessions.workflow(sessionId),
          api.sessions.modelOutputs(sessionId),
          api.sessions.models(sessionId),
        ]);
        if (workflow?.steps?.length) {
          const sessionModels = models?.items || [];
          const hasModelInRepo = hasRepoModel(sessionModels);
          const deploymentDone = isDeploymentSuccessText(finalText) || hasDeployedModel(sessionModels);
          setWorkflowVersions(prev => [{
            version: prev[0]?.version || '当前会话',
            repoStatus: hasModelInRepo ? '已入库' : (prev[0]?.repoStatus || '未入库'),
            deployStatus: deploymentDone ? '已部署' : (prev[0]?.deployStatus || '未部署'),
            pipelineId: prev[0]?.pipelineId,
            steps: mapBackendWorkflowSteps(workflow.steps, prev[0]?.steps),
          }]);
        }
        setSessionArtifacts(prev => ({
          ...prev,
          [sessionId]: {
            modelItems: outputs?.modelItems || [],
            allItems: (outputs as any)?.allItems || [],
          },
        }));
      } catch (refreshErr) {
        console.warn('Failed to refresh session workflow:', refreshErr);
      }

      const pipelineIdMatch = finalText.match(/流水线ID:\s*(pl_[a-f0-9]+)/);
      if (pipelineIdMatch) {
        setPollingPipelineIds(prev => new Set(prev).add(pipelineIdMatch[1]));
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User cancelled
        if (streamingText) {
          setSessions((prev) =>
            prev.map((s) => {
              if (s.id !== sessionId) return s;
              return {
                ...s,
                _streamingText: undefined,
                messages: [...s.messages, { role: 'ai' as const, text: streamingText + '\n\n_(已中断)_', timestamp: new Date().toISOString() }],
              };
            })
          );
        }
      } else {
        const errorMsg = err instanceof Error ? err.message : '未知错误';
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id !== sessionId) return s;
            return {
              ...s,
              messages: [...s.messages, { role: 'ai' as const, text: `⚠️ 请求出错: ${errorMsg}\n\n请检查网络或更换模型后重试。`, timestamp: new Date().toISOString() }],
            };
          })
        );
      }
    } finally {
      setIsStreaming(false);
      setStreamingSessionId(null);
      setStreamingText('');
      // 清除残留的 _streamingText
      setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, _streamingText: undefined } : s));
      abortRef.current = null;
    }
  };

  useEffect(() => {
    if (!pendingUploadSend || isStreaming || currentSessionId !== pendingUploadSend.sessionId) return;
    const pending = pendingUploadSend;
    setPendingUploadSend(null);
    handleSend(pending.message, undefined, pending.files);
  }, [pendingUploadSend, isStreaming, currentSessionId]);

  const handleStopStream = () => {
    abortRef.current?.abort();
  };

  const handleNewSession = async () => {
    try {
      const created = await api.sessions.create('新建会话');
      const sessionId = created.sessionId;
      const now = new Date();
      const t = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
      const newSession: ChatSession = {
        id: sessionId,
        title: '新建会话',
        status: '待开始',
        progress: '等待输入',
        time: t,
        createdAt: now.toISOString(),
        messages: [
          { role: 'ai', text: `你好！我是${assistantSettings.name}，你的金融智能建模助手。\n\n我可以帮你完成从数据分析到模型部署的全流程建模。请告诉我：\n\n1. 📊 **你的建模目标**（如：金融反欺诈、信用评分、客户流失预测）\n2. 📁 **上传数据文件**（支持 CSV/XLSX/JSON）\n\n我将为你定制建模路线，逐步引导你完成模型构建。建模完成后，我会询问你任务命名和是否要入库保存。` },
        ],
      };
      setSessions([newSession, ...sessions]);
      setCurrentSessionId(newSession.id);
      if (!leftPanelOpen) setLeftPanelOpen(true);
    } catch {
      // 后端创建失败，用本地 ID 兜底
      const now = new Date();
      const t = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
      const newSession: ChatSession = {
        id: `s${Date.now()}`,
        title: '新建会话',
        status: '待开始',
        progress: '等待输入',
        time: t,
        createdAt: now.toISOString(),
        messages: [],
      };
      setSessions([newSession, ...sessions]);
      setCurrentSessionId(newSession.id);
    }
  };

  const handleRenameSession = (id: string) => {
    const session = sessions.find((s) => s.id === id);
    if (!session) return;
    setRenamingId(id);
    setRenameValue(session.title);
  };

  const handleRenameConfirm = async () => {
    if (!renamingId || !renameValue.trim()) return;
    try {
      // 调用后端 API 更新会话标题
      await api.sessions.update(renamingId, renameValue.trim());
      // 更新前端状态
      setSessions((prev) =>
        prev.map((s) => (s.id === renamingId ? { ...s, title: renameValue.trim() } : s))
      );
      toast.success('会话已重命名');
    } catch (err) {
      console.error('Failed to rename session:', err);
      toast.error('重命名失败，请稍后重试');
    } finally {
      setRenamingId(null);
      setRenameValue('');
    }
  };

  const handleDeleteSession = async (id: string) => {
    // 检查该会话关联的任务是否已入库
    const relatedTasks = platform.tasks.filter((t) => t.sessionId === id);
    const archivedTasks = relatedTasks.filter((t) => t.inRepo);
    if (archivedTasks.length > 0) {
      toast.error('无法删除该会话', { description: `该会话下有 ${archivedTasks.length} 个已入库任务，数据需要保留` });
      return;
    }

    // 确认删除
    if (!confirm('确定要删除该会话吗？\n删除后将同时清除关联的建模任务和后端数据，且不可恢复。')) return;

    try {
      // 1. 调用后端API删除session数据（pipeline + 上传文件）
      try {
        await api.sessions.delete(id);
      } catch {
        // session数据已不存在（可忽略）
      }

      // 2. 删除关联的未入库任务
      for (const task of relatedTasks) {
        if (!task.inRepo) {
          platform.updateTask(task.id, { status: 'failed' });
          // Remove from tasks list via setTasks (tasks page)
          window.dispatchEvent(new CustomEvent('tasks:delete-task', { detail: { taskId: task.id } }));
        }
      }

      // 3. 从前端 state 中移除会话
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (id === currentSessionId) {
        const remaining = sessions.filter((s) => s.id !== id);
        if (remaining.length > 0) setCurrentSessionId(remaining[0].id);
      }
      toast.success('会话已删除', { description: '关联的任务和数据已一并清除' });
    } catch (err) {
      console.error('Failed to delete session:', err);
      toast.error('删除会话失败', { description: String(err) });
    }
  };

  const handlePinSession = (id: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, pinned: !s.pinned } : s))
    );
  };

  // Version-aware workflow: each version has its own 4-step progress + repo/deploy status
  // Driven by tool_results metadata from SSE, NOT by keyword guessing
  const [workflowVersions, setWorkflowVersions] = useState<WorkflowVersion[]>([createEmptyWorkflowVersion()]);
  const [activeVersionIdx, setActiveVersionIdx] = useState(0);
  const prevVersionCountRef = useRef(1);

  // Step index to step id mapping (1-based index from backend)
  const stepIndexToId: Record<number, string> = { 1: 'data', 2: 'feature', 3: 'train', 4: 'eval' };
  const stepOutputs: Record<string, string> = {
    data: '已加载交易数据',
    feature: '筛选出有效特征',
    train: '模型训练完成',
    eval: '模型评估完成',
  };

  // Process tool_results metadata from SSE messages to update workflow state
  const processToolResults = useCallback((tools: Array<{toolName: string; success: boolean; data: Record<string, unknown>}>) => {
    setWorkflowVersions((prevVersions) => {
      const versions = [...prevVersions];
      let changed = false;

      for (const tool of tools) {
        if (!tool.success) continue;
        const toolNameText = String(tool.toolName || '');
        const toolDataText = JSON.stringify(tool.data || {});
        const isDeployTool = /deploy|service|instance|部署|服务/i.test(toolNameText) || isDeploymentSuccessText(toolDataText);

        if (isDeployTool) {
          const idx = Math.min(activeVersionIdx, versions.length - 1);
          if (versions[idx]) {
            versions[idx] = { ...versions[idx], deployStatus: '已部署' };
            changed = true;
          }
        }

        if (tool.toolName === 'UPLOAD_DATA') {
          // Data uploaded - mark step 1 as running on current version
          const idx = Math.min(activeVersionIdx, versions.length - 1);
          if (versions[idx]) {
            versions[idx] = {
              ...versions[idx],
              steps: versions[idx].steps.map((s, i) =>
                i === 0 ? { ...s, status: 'running' as const, detail: '正在读取数据文件...' } : s
              ),
            };
            changed = true;
          }
        }

        if (tool.toolName === 'CREATE_PIPELINE') {
          // Pipeline created - associate pipelineId with current version
          const pipelineId = tool.data.pipelineId as string;
          const modelName = (tool.data.modelName as string) || `建模任务 ${pipelineId}`;
          const idx = Math.min(activeVersionIdx, versions.length - 1);
          if (versions[idx]) {
            versions[idx] = { ...versions[idx], pipelineId };
            changed = true;
          }
          // Create a corresponding task entry
          const taskId = `pipeline-${pipelineId}`;
          const existingTask = platform.tasks.find(t => t.id === taskId);
          if (!existingTask) {
            platform.addTask({
              id: taskId,
              name: modelName,
              description: `基于流水线 ${pipelineId} 的${modelName}`,
              status: 'running' as const,
              sessionId: currentSessionId || undefined,
              inRepo: false,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              dataFiles: [],
              modelFiles: [],
              codeFiles: [],
            });
          }
        }

        if (tool.toolName === 'EXECUTE_STEP') {
          const step = tool.data.step as number;
          const stepId = stepIndexToId[step];
          if (!stepId) continue;

          const pipelineId = tool.data.pipelineId as string;
          // Find the version that owns this pipeline, or use current version
          let vIdx = versions.findIndex((v) => v.pipelineId === pipelineId);
          if (vIdx === -1) vIdx = Math.min(activeVersionIdx, versions.length - 1);

          if (versions[vIdx]) {
            versions[vIdx] = {
              ...versions[vIdx],
              pipelineId: versions[vIdx].pipelineId || pipelineId,
              steps: versions[vIdx].steps.map((s, i) => {
                const stepIdx = ['data', 'feature', 'train', 'eval'].indexOf(stepId);
                if (i < stepIdx) {
                  // Previous steps should be completed
                  return s.status !== 'completed' ? { ...s, status: 'completed' as const, output: stepOutputs[s.id], detail: undefined } : s;
                } else if (i === stepIdx) {
                  // Current step completed
                  return { ...s, status: 'completed' as const, output: stepOutputs[stepId], detail: undefined };
                }
                return s;
              }),
            };
            changed = true;
          }
        }

        if (tool.toolName === 'RETRAIN') {
          // Retrain creates a new version
          const pipelineId = tool.data.pipelineId as string;
          const newVersionNum = versions.length + 1;
          const newVersion = `${newVersionNum}.0v`;
          const currentStep = (tool.data.currentStep as number) || 4;
          versions.push({
            version: newVersion,
            pipelineId,
            steps: [
              { id: 'data', name: '数据接入', status: 'completed' as const, output: '已加载交易数据' },
              { id: 'feature', name: '特征工程', status: 'completed' as const, output: '筛选出有效特征' },
              { id: 'train', name: '模型训练', status: 'completed' as const, output: '重训完成' },
              { id: 'eval', name: '模型评估', status: currentStep >= 4 ? 'completed' as const : 'running' as const, output: currentStep >= 4 ? '评估完成' : undefined, detail: currentStep < 4 ? '正在评估...' : undefined },
            ],
            repoStatus: '未入库',
            deployStatus: '未部署',
          });
          setActiveVersionIdx(versions.length - 1);
          changed = true;
        }

        if (tool.toolName === 'CONFIRM_PIPELINE') {
          // Model archived - update repo status AND push to model repository
          const pipelineId = tool.data.pipelineId as string;
          const modelName = (tool.data.modelName as string) || '新训练模型';
          const modelType = (tool.data.modelType as string) || '';
          const targetColumn = (tool.data.targetColumn as string) || '';
          const sampleCount = (tool.data.sampleCount as number) || 0;
          const featuresCount = (tool.data.featuresCount as number) || 0;
          const metrics = (tool.data.metrics as Record<string, number>) || {};
          let vIdx = versions.findIndex((v) => v.pipelineId === pipelineId);
          if (vIdx === -1) vIdx = Math.min(activeVersionIdx, versions.length - 1);
          if (versions[vIdx]) {
            versions[vIdx] = { ...versions[vIdx], repoStatus: '已入库' };
            changed = true;
            // Push to model repository via platform context with real backend data
            try {
              const taskId = `pipeline-${pipelineId}`;
              // First create a task entry if it doesn't exist, then push to repo
              const existingTask = platform.tasks.find(t => t.id === taskId);
              if (!existingTask) {
                platform.addTask({
                  id: taskId,
                  name: modelName,
                  description: `基于流水线 ${pipelineId} 的${modelName}`,
                  status: 'completed' as const,
                  sessionId: currentSessionId || undefined,
                  inRepo: false,
                  createdAt: new Date().toISOString(),
                  updatedAt: new Date().toISOString(),
                  dataFiles: [],
                  modelFiles: [],
                  codeFiles: [],
                });
              }
              // Mark task as in repo and update status
              const task = platform.tasks.find(t => t.id === taskId);
              if (task && !task.inRepo) {
                platform.updateTask(taskId, { inRepo: true, status: 'completed' });
              }
              // Infer scene name from target column and model name
              const sceneName = targetColumn.includes('fraud') || targetColumn.includes('欺诈') || modelName.includes('反欺诈')
                ? '反欺诈检测'
                : targetColumn.includes('电诈') || targetColumn.includes('诈骗') || modelName.includes('反诈')
                ? '电信网络反诈'
                : targetColumn.includes('default') || targetColumn.includes('违约') || modelName.includes('违约')
                ? '信用违约预测'
                : targetColumn.includes('churn') || targetColumn.includes('流失') || modelName.includes('流失')
                ? '客户留存分析'
                : targetColumn.includes('credit') || targetColumn.includes('信用') || modelName.includes('信用')
                ? '信用风险评估'
                : targetColumn.includes('distress') || targetColumn.includes('困境')
                ? '财务困境预测'
                : '金融风控分析';
              // Map model type to framework string
              const frameworkMap: Record<string, string> = {
                'RandomForest': 'sklearn / RandomForestClassifier',
                'LogisticRegression': 'sklearn / LogisticRegression',
                'GradientBoosting': 'sklearn / GradientBoostingClassifier',
                'XGBoost': 'xgboost / XGBClassifier',
                'LightGBM': 'lightgbm / LGBMClassifier',
              };
              const framework = frameworkMap[modelType] || (modelType ? `sklearn / ${modelType}` : 'sklearn / LightGBM');
              platform.pushToRepo(taskId, {
                modelName,
                sceneName,
                modelType: 'classification',
                framework,
                sampleCount,
                featuresCount,
                metrics,
                version: '1.0.0',
              });
            } catch (e) {
              console.warn('Failed to push to repo:', e);
            }
          }
        }
      }

      return changed ? versions : prevVersions;
    });
  }, [activeVersionIdx, stepIndexToId]);

  // Track which messages have already been processed to avoid duplicates
  const processedToolMetaMsgsRef = useRef<Set<string>>(new Set());

  // Track when streaming ends to process tool_results from message metadata
  useEffect(() => {
    if (isStreaming) return;
    const session = sessions.find((s) => s.id === currentSessionId);
    if (!session) return;

    // Check the last AI message for tool_results metadata
    const lastAiMsg = [...session.messages].reverse().find((m) => m.role === 'ai');
    if (!lastAiMsg) return;

    // Deduplicate: skip if this message was already processed during streaming
    const msgKey = `${currentSessionId}-${lastAiMsg.timestamp}`;
    if (processedToolMetaMsgsRef.current.has(msgKey)) return;

    // If the message has toolMeta stored, process it
    const toolMeta = (lastAiMsg as Record<string, unknown>).toolMeta;
    if (Array.isArray(toolMeta) && toolMeta.length > 0) {
      processedToolMetaMsgsRef.current.add(msgKey);
      processToolResults(toolMeta as Array<{toolName: string; success: boolean; data: Record<string, unknown>}>);
    }

    // Also update model list in session if training completed
    const existingModels = session.models || [];
    const completedSteps = workflowVersions[activeVersionIdx]?.steps.filter(s => s.status === 'completed') || [];
    if (false && completedSteps.length >= 3 && existingModels.length === 0) {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSessionId
            ? { ...s, models: [...(s.models || []), {
                name: '训练模型',
                version: workflowVersions[activeVersionIdx]?.version || '1.0v',
                status: completedSteps.length >= 4 ? 'deployed' : 'running',
                time: new Date().toLocaleString('zh-CN'),
              }] }
            : s
        )
      );
    }
  }, [isStreaming, currentSessionId, sessions, activeVersionIdx, workflowVersions, processToolResults]);

  const agentSteps = useMemo(() => {
    const activeVersion = workflowVersions[activeVersionIdx] || workflowVersions[0];
    return activeVersion?.steps || [
      { id: 'data', name: '数据接入', status: 'pending' as const, duration: undefined, output: undefined, detail: undefined },
      { id: 'feature', name: '特征工程', status: 'pending' as const, duration: undefined, output: undefined, detail: undefined },
      { id: 'train', name: '模型训练', status: 'pending' as const, duration: undefined, output: undefined, detail: undefined },
      { id: 'eval', name: '模型评估', status: 'pending' as const, duration: undefined, output: undefined, detail: undefined },
    ];
  }, [workflowVersions, activeVersionIdx]);

  // Dynamic right-panel data driven by conversation progress
  // Fetch real task data from API when session has a linked task
  const [linkedTask, setLinkedTask] = useState<{id: string; name: string; status: string; dataFiles: string[]; modelFiles: string[]} | null>(null);
  useEffect(() => {
    if (!currentSessionId) { setLinkedTask(null); return; }
    setLinkedTask(null);
    return;
    const fetchLinkedTask = async () => {
      try {
        const pipelineData = await api.pipelines.list({ page: 1, pageSize: 1 });
        const items = pipelineData?.items || [];
        if (items.length > 0) {
          const t: any = items[0];
          setLinkedTask({ id: String(t.id), name: String(t.name || '未命名'), status: String(t.status || 'pending'), dataFiles: [], modelFiles: [] });
        } else { setLinkedTask(null); }
      } catch { setLinkedTask(null); }
    };
    fetchLinkedTask();
  }, [currentSessionId, toBackendModels]);

  // 监听来自 tasks 页面的级联删除事件
  useEffect(() => {
    const handleDeleteSessionEvent = (e: Event) => {
      const { sessionId } = (e as CustomEvent).detail;
      if (sessionId) handleDeleteSession(sessionId);
    };
    window.addEventListener('copilot:delete-session', handleDeleteSessionEvent);
    return () => window.removeEventListener('copilot:delete-session', handleDeleteSessionEvent);
  }, [sessions, currentSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const legacyPanelData = useMemo(() => {
    const session = sessions.find((s) => s.id === currentSessionId);
    if (!session) return { dataFileCount: 0, dataSize: 0, modelFileCount: 0, featureCount: 0, sampleCount: 0, taskStatus: 'pending' as const, taskName: '', metrics: null as { auc: number; ks: number; psi: number } | null, taskId: '' };

    // Use real task data if available from API
    if (linkedTask) {
      const dataFileCount = linkedTask.dataFiles.length;
      const modelFileCount = linkedTask.modelFiles.length;
      const sampleCount = dataFileCount > 0 ? 1256842 : 0;
      const featureCount = modelFileCount > 0 ? 32 : dataFileCount > 0 ? 156 : 0;
      let taskStatus: 'pending' | 'running' | 'completed' = 'pending';
      if (linkedTask.status === 'completed' || linkedTask.status === 'archived') taskStatus = 'completed';
      else if (linkedTask.status === 'running') taskStatus = 'running';
      const metrics = modelFileCount > 0 ? { auc: 0.952, ks: 0.52, psi: 0.04 } : null;
      return { dataFileCount, dataSize: dataFileCount > 0 ? 2.4 : 0, modelFileCount, featureCount, sampleCount, taskStatus, taskName: linkedTask.name, metrics, taskId: linkedTask.id };
    }

    // Fallback: derive from agentSteps (demo mode)
    const completedSteps = agentSteps.filter((s) => s.status === 'completed').length;
    const dataFileCount = completedSteps >= 1 ? 3 : 0;
    const dataSize = completedSteps >= 1 ? 2.4 : 0;
    const sampleCount = completedSteps >= 1 ? 1256842 : 0;
    const featureCount = completedSteps >= 2 ? 32 : completedSteps >= 1 ? 156 : 0;
    const modelFileCount = completedSteps >= 3 ? 4 : completedSteps >= 2 ? 1 : 0;
    let taskStatus: 'pending' | 'running' | 'completed' = 'pending';
    if (completedSteps >= 4) taskStatus = 'completed';
    else if (completedSteps >= 1) taskStatus = 'running';
    const taskName = session.title || '新建模任务';
    let metrics: { auc: number; ks: number; psi: number } | null = null;
    if (completedSteps >= 4) metrics = { auc: 0.952, ks: 0.52, psi: 0.04 };
    else if (completedSteps >= 3) metrics = { auc: 0.948, ks: 0.49, psi: 0.06 };
    return { dataFileCount, dataSize, modelFileCount, featureCount, sampleCount, taskStatus, taskName, metrics, taskId: '' };
  }, [currentSessionId, sessions, agentSteps, linkedTask]);

  void legacyPanelData;

  const panelData = useMemo(() => {
    const session = sessions.find((s) => s.id === currentSessionId);
    const empty = { dataFileCount: 0, dataSize: 0, dataSizeLabel: '暂无', modelFileCount: 0, featureCount: 0, sampleCount: 0, taskStatus: 'pending' as const, taskName: '', metrics: null as { auc: number; ks: number; psi: number } | null, taskId: '' };
    if (!session) return empty;
    const files = (session.files || []).filter((file) => file.type === 'input');
    const artifacts = currentSessionId ? sessionArtifacts[currentSessionId] : undefined;
    const dataFileCount = files.length;
    const totalBytes = files.reduce((sum, file) => sum + Number((file as any).sizeBytes || 0), 0);
    const sampleCount = files.reduce((sum, file) => sum + Number((file as any).rows || 0), 0);
    const modelFileCount = artifacts?.modelItems?.length || session.models?.length || 0;
    let taskStatus: 'pending' | 'running' | 'completed' = 'pending';
    if (modelFileCount > 0) taskStatus = 'completed';
    else if (dataFileCount > 0 || agentSteps.some((step) => step.status === 'running')) taskStatus = 'running';
    return {
      dataFileCount,
      dataSize: totalBytes,
      dataSizeLabel: totalBytes > 0 ? formatFileSize(totalBytes) : '暂无',
      modelFileCount,
      featureCount: 0,
      sampleCount,
      taskStatus,
      taskName: session.title || '新建模任务',
      metrics: null,
      taskId: linkedTask?.id || '',
    };
  }, [currentSessionId, sessions, agentSteps, linkedTask, sessionArtifacts]);

  const filteredSessions = sessions.filter(
    (s) => !searchValue || s.title.includes(searchValue) || s.progress.includes(searchValue)
  );

  const currentModelInfo = { id: 'agent', name: 'FinForge AI' };

  // 无会话时显示加载
  if (!currentSession) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-56px)]">
        <div className="text-muted-foreground animate-pulse">正在初始化会话...</div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">
      {/* Left: Session List - Fixed, Collapsible. On mobile: overlay drawer */}
      <div
        className={`relative flex shrink-0 flex-col border-r border-border/60 bg-white transition-all duration-300 ease-in-out ${
          leftPanelOpen ? 'max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50 max-md:w-[280px] max-md:shadow-xl w-[280px]' : 'w-0'
        }`}
        style={{ overflow: 'hidden' }}
      >
        {/* Mobile backdrop */}
        {leftPanelOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/30 md:hidden"
            onClick={() => setLeftPanelOpen(false)}
          />
        )}
        <div className="relative z-50 flex h-full min-w-[280px] flex-col overflow-hidden">
          {/* Fixed top: Copilot avatar + Nav */}
          <div className="shrink-0 space-y-2 px-3 pt-3 pb-2">
            {/* Copilot avatar - click to start new conversation */}
            <button
              onClick={handleNewSession}
              onContextMenu={(e) => { e.preventDefault(); setTempAssistantSettings(assistantSettings); setShowAssistantSettings(true); }}
              className="group flex w-full items-center gap-2.5 rounded-lg px-2 py-2 transition-colors hover:bg-blue-50/80"
            >
              <div className="transition-transform group-hover:scale-105">
                <RobotAvatar size={36} avatarId={assistantSettings.avatarId} avatarUrl={assistantSettings.avatarUrl} />
              </div>
              <div className="flex flex-col items-start overflow-hidden">
                <span className="text-sm font-semibold text-foreground truncate">{assistantSettings.name}</span>
                <span className="text-[11px] text-muted-foreground">点击新对话 · 右键设置</span>
              </div>
            </button>
            {/* Nav items removed — now in top header 建模平台 dropdown */}
            <div className="border-t border-border/40" />
          </div>

          {/* Search */}
          <div className="relative shrink-0 mx-3 mb-2">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索对话"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              className="pl-9 h-8 text-xs"
            />
          </div>

          {/* Scrollable conversation list */}
          <div className="flex-1 overflow-y-auto scroll-smooth px-2 pb-3 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border/60 hover:[&::-webkit-scrollbar-thumb]:bg-border">
            <div className="space-y-0.5 pr-1">
              {/* Pinned section */}
              {filteredSessions.some((s) => s.pinned) && (
                <>
                  <div className="flex items-center gap-1.5 px-2 pt-2 pb-1">
                    <Pin className="h-3 w-3 text-muted-foreground" />
                    <span className="text-[11px] font-medium text-muted-foreground">已置顶</span>
                  </div>
                  {filteredSessions.filter((s) => s.pinned).map((session) => (
                    <SessionCard
                      key={session.id}
                      session={session}
                      isActive={session.id === currentSessionId}
                      renamingId={renamingId}
                      renameValue={renameValue}
                      onSelect={() => setCurrentSessionId(session.id)}
                      onRename={() => handleRenameSession(session.id)}
                      onRenameValueChange={setRenameValue}
                      onRenameConfirm={handleRenameConfirm}
                      onDelete={() => handleDeleteSession(session.id)}
                      onPin={() => handlePinSession(session.id)}
                    />
                  ))}
                  <div className="my-1.5 border-t border-border/40" />
                </>
              )}
              {/* All sessions */}
              <div className="flex items-center gap-1.5 px-2 pt-1 pb-1">
                <span className="text-[11px] font-medium text-muted-foreground">全部对话</span>
              </div>
              {filteredSessions.filter((s) => !s.pinned).map((session) => (
                <SessionCard
                  key={session.id}
                  session={session}
                  isActive={session.id === currentSessionId}
                  renamingId={renamingId}
                  renameValue={renameValue}
                  onSelect={() => setCurrentSessionId(session.id)}
                  onRename={() => handleRenameSession(session.id)}
                  onRenameValueChange={setRenameValue}
                  onRenameConfirm={handleRenameConfirm}
                  onDelete={() => handleDeleteSession(session.id)}
                  onPin={() => handlePinSession(session.id)}
                />
              ))}
            </div>
          </div>

          {/* Bottom: User + Notification (same row, icon only) */}
          <div className="mt-auto shrink-0 border-t border-gray-100 px-3 py-2.5 flex items-center justify-between">
            <button
              className="flex items-center justify-center rounded-lg p-1.5 transition-all duration-200 hover:bg-gray-100 hover:scale-110 active:scale-95"
              title="张三"
            >
              <Avatar className="h-8.5 w-8.5 shrink-0 border-2 border-blue-200 bg-gradient-to-br from-blue-500 to-indigo-600">
                <AvatarFallback className="bg-transparent text-xs font-bold text-white">张</AvatarFallback>
              </Avatar>
            </button>
            <NotificationCenter />
          </div>
        </div>
      </div>

      {/* Left Panel Toggle */}
      <button
        onClick={() => setLeftPanelOpen(!leftPanelOpen)}
        className="group relative z-10 flex h-8 w-6 shrink-0 items-center justify-center self-center rounded-r-md border border-l-0 border-border/60 bg-white text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        title={leftPanelOpen ? '收起左栏' : '展开左栏'}
      >
        {leftPanelOpen ? (
          <PanelLeftClose className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
        ) : (
          <PanelLeftOpen className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        )}
      </button>

      {/* Center: Chat Area */}
      <div
        className="flex flex-1 flex-col bg-white/50 overflow-hidden relative"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Drag & Drop Overlay */}
        {isDragOver && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-blue-50/80 backdrop-blur-sm border-2 border-dashed border-blue-400 rounded-lg m-2">
            <div className="flex flex-col items-center gap-3 text-blue-600">
              <Upload className="h-10 w-10 animate-bounce" />
              <div className="text-center">
                <p className="text-lg font-semibold">释放文件以上传</p>
                <p className="text-sm text-blue-500">支持 CSV / Excel / Parquet / JSON / TXT</p>
              </div>
            </div>
          </div>
        )}
        {/* Chat Header */}
        <div className="border-b border-border/60 px-3 py-2 sm:px-5 sm:py-2.5 shrink-0 flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
          <h2 className="text-base sm:text-xl font-semibold truncate">{currentSession?.title}</h2>
          <div className="flex items-center gap-2 sm:gap-4 mt-0.5 min-w-0 overflow-x-auto">
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {formatSessionCreatedAt(currentSession?.createdAt)}
            </span>
            {/* Files Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors rounded-md px-2 py-1 hover:bg-accent/50">
                  <FileText className="h-3.5 w-3.5" />
                  数据文件 ({(currentSession?.files || []).length})
                  <ChevronDown className="h-3 w-3" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-80 p-0">
                <div className="p-2 border-b">
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input
                      className="w-full rounded-md border bg-background px-7 py-1.5 text-xs outline-none focus:ring-1 focus:ring-ring"
                      placeholder="搜索文件..."
                      value={fileSearch}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFileSearch(e.target.value)}
                    />
                  </div>
                </div>
                <div className="max-h-60 overflow-y-auto">
                  {(currentSession?.files || [])
                    .filter((f: { name: string }) => f.name.toLowerCase().includes(fileSearch.toLowerCase()))
                    .map((f: { name: string; type: string; size: string | number; time: string }, fi: number) => (
                      <div key={fi} className="flex items-center gap-2 px-3 py-2 text-xs hover:bg-accent/50 transition-colors">
                        {f.type === 'input'
                          ? <Upload className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                          : <Download className="h-3.5 w-3.5 text-green-500 shrink-0" />
                        }
                        <div className="min-w-0 flex-1">
                          <div className="font-medium truncate">{f.name}</div>
                          <div className="text-muted-foreground">{f.size} · {f.time}</div>
                        </div>
                        <span className={f.type === 'input' ? 'text-blue-500' : 'text-green-500'}>{f.type === 'input' ? '输入' : '输出'}</span>
                      </div>
                    ))}
                  {(currentSession?.files || []).filter((f: { name: string }) => f.name.toLowerCase().includes(fileSearch.toLowerCase())).length === 0 && (
                    <div className="px-3 py-4 text-xs text-center text-muted-foreground">无匹配文件</div>
                  )}
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
            {/* Models Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors rounded-md px-2 py-1 hover:bg-accent/50">
                  <Cpu className="h-3.5 w-3.5" />
                  参与模型 ({(currentSession?.models || []).length})
                  <ChevronDown className="h-3 w-3" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-80 p-0">
                <div className="p-2 border-b">
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input
                      className="w-full rounded-md border bg-background px-7 py-1.5 text-xs outline-none focus:ring-1 focus:ring-ring"
                      placeholder="搜索模型..."
                      value={modelSearch}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setModelSearch(e.target.value)}
                    />
                  </div>
                </div>
                <div className="max-h-60 overflow-y-auto">
                  {(currentSession?.models || [])
                    .filter((m: { name: string }) => m.name.toLowerCase().includes(modelSearch.toLowerCase()))
                    .map((m: { name: string; version: string; status: string; time: string }, mi: number) => (
                      <div key={mi} className="flex items-center gap-2 px-3 py-2 text-xs hover:bg-accent/50 transition-colors">
                        <Cpu className="h-3.5 w-3.5 text-purple-500 shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="font-medium truncate">{m.name} <span className="text-muted-foreground">{m.version}</span></div>
                          <div className="text-muted-foreground">{m.time}</div>
                        </div>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          m.status === 'running' ? 'bg-green-100 text-green-700' :
                          m.status === 'stopped' ? 'bg-gray-100 text-gray-600' :
                          m.status === 'error' ? 'bg-red-100 text-red-700' :
                          'bg-blue-100 text-blue-700'
                        }`}>
                          {m.status === 'running' ? '运行中' : m.status === 'stopped' ? '已停止' : m.status === 'error' ? '异常' : m.status}
                        </span>
                      </div>
                    ))}
                  {(currentSession?.models || []).filter((m: { name: string }) => m.name.toLowerCase().includes(modelSearch.toLowerCase())).length === 0 && (
                    <div className="px-3 py-4 text-xs text-center text-muted-foreground">无匹配模型</div>
                  )}
                </div>
              </DropdownMenuContent>
            </DropdownMenu>

          </div>
          </div>
          <button
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
            className="p-1.5 rounded-md hover:bg-accent/50 text-muted-foreground hover:text-foreground transition-colors shrink-0"
            title={rightPanelOpen ? '收起面板' : '展开面板'}
          >
            {rightPanelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
          </button>
          {/* Chat search */}
          <Popover open={chatSearchOpen} onOpenChange={setChatSearchOpen}>
            <PopoverTrigger asChild>
              <button
                className="p-1.5 rounded-md hover:bg-accent/50 text-muted-foreground hover:text-foreground transition-colors shrink-0 mt-0.5"
                title="搜索对话内容"
              >
                <Search className="h-4 w-4" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-96 p-0">
              <div className="p-3 border-b">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    className="w-full rounded-md border bg-background pl-8 pr-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
                    placeholder="搜索对话内容..."
                    value={chatSearchQuery}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setChatSearchQuery(e.target.value)}
                    autoFocus
                  />
                </div>
                {chatSearchQuery && (
                  <div className="mt-2 flex gap-1.5 flex-wrap">
                    {(['全部', 'AI回复', '我的消息'] as const).map((tab) => (
                      <button
                        key={tab}
                        className={`px-2 py-0.5 rounded-full text-xs transition-colors ${
                          chatSearchTab === tab
                            ? 'bg-blue-100 text-blue-700 font-medium'
                            : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                        }`}
                        onClick={() => setChatSearchTab(tab)}
                      >
                        {tab}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="max-h-72 overflow-y-auto">
                {chatSearchQuery && chatSearchResults.length === 0 && (
                  <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                    未找到相关内容
                  </div>
                )}
                {chatSearchResults.map((result, ri) => (
                  <button
                    key={ri}
                    className="w-full text-left px-3 py-2.5 hover:bg-accent/50 transition-colors border-b last:border-b-0"
                    onClick={() => {
                      setChatSearchOpen(false);
                      setChatSearchQuery('');
                    }}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        result.role === 'ai' ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {result.role === 'ai' ? assistantSettings.name : '你'}
                      </span>
                      <span className="text-xs text-muted-foreground">{result.timestamp ? formatTime(result.timestamp) : ''}</span>
                    </div>
                    <p className="text-sm text-foreground line-clamp-2">{highlightMatch(result.text, chatSearchQuery)}</p>
                  </button>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        </div>
        {/* Messages */}
        <div
          className="flex-1 overflow-y-auto scroll-smooth relative"
          onWheel={(e) => { e.stopPropagation(); }}
        >
          <div className="mx-auto max-w-[960px] space-y-5 py-6 px-3 sm:px-6 md:px-10">
            {/* Drift Alert Banner */}
            {driftAlert && (
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5">
                    <Siren className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-widest text-blue-500">
                        Drift Alert Context
                      </p>
                      <p className="mt-1 text-sm font-semibold text-blue-900">
                        已从模型服务告警跳入，自动携带"线上模型漂移"上下文
                      </p>
                      <p className="mt-0.5 text-xs text-blue-600">
                        Copilot 将自动启动重训练流程，修复线上模型精准率偏移问题
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setDriftAlert(false)}
                    className="shrink-0 rounded-md p-1 text-blue-400 hover:bg-blue-100 hover:text-blue-600 transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
            {currentSession?.messages.map((msg, i) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={i}
                  className={`animate-message-in group/msg relative ${isUser ? 'flex flex-col items-end' : 'flex flex-col items-start'}`}
                >
                  <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                    {/* Avatar */}
                    {!isUser && (
                      <div className="shrink-0 mt-0.5">
                        <RobotAvatar size={48} avatarId={assistantSettings.avatarId} avatarUrl={assistantSettings.avatarUrl} />
                      </div>
                    )}
                    {isUser && (
                      <div className="shrink-0 mt-0.5">
                        <UserAvatar size={48} name={userInfo.initial} />
                      </div>
                    )}
                    {/* Bubble */}
                    <div className="max-w-[80%] sm:max-w-[80%]">
                      {/* Name + Timestamp label */}
                      <div className={`flex items-baseline gap-1.5 mb-0.5 px-1 ${isUser ? 'flex-row-reverse' : ''}`}>
                        <span className="text-[12px] font-medium text-gray-600">
                          {isUser ? '你' : assistantSettings.name}
                        </span>
                        {msg.timestamp && (
                          <span className="text-[11px] text-gray-400">
                            {new Date(msg.timestamp).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                      </div>
                      {/* Thinking Bubble - show AI reasoning process */}
                      {!isUser && msg.thinking && (
                        <ThinkingBubble steps={msg.thinking.steps} duration={msg.thinking.duration} />
                      )}
                      <div
                        className={`rounded-2xl px-4 py-3 text-[14px] leading-relaxed break-words ${
                          isUser
                            ? 'bg-blue-600 text-white rounded-br-md'
                            : 'bg-gray-100 text-gray-800 rounded-bl-md'
                        }`}
                      >
                        {/* 文件卡片 - 在消息文本上方显示 */}
                        {isUser && msg.files && msg.files.length > 0 && (
                          <div className="flex flex-col gap-1.5 mb-2">
                            {msg.files.map((f, fi) => (
                              <div key={fi} className="flex items-center gap-2 bg-white/15 rounded-lg px-3 py-2 text-xs">
                                <FileSpreadsheet className="h-4 w-4 shrink-0 text-green-300" />
                                <div className="flex-1 min-w-0">
                                  <div className="font-medium truncate">{f.name}</div>
                                  <div className="text-white/60">{f.size} · {f.type?.toUpperCase()}</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        {isUser ? msg.text : <MarkdownRenderer content={msg.text} variant={isUser ? 'user' : 'assistant'} />}
                      </div>
                    </div>
                  </div>
                  {/* Hover actions */}
                  <div className={`flex items-center gap-0.5 mt-1 opacity-0 group-hover/msg:opacity-100 transition-opacity duration-150 ${isUser ? 'mr-14' : 'ml-14'}`}>
                    <button
                      onClick={() => { navigator.clipboard.writeText(msg.text); toast.success('已复制到剪贴板'); }}
                      className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                      title="复制"
                    >
                      <Copy className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => { setQuotedMessage({ content: msg.text, role: msg.role }); }}
                      className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                      title="引用"
                    >
                      <Quote className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => { const text = `${assistantSettings.name}: ${msg.text}`; navigator.clipboard.writeText(text); toast.success('分享内容已复制'); }}
                      className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                      title="分享"
                    >
                      <Share2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => { toast.success('已收藏'); }}
                      className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                      title="收藏"
                    >
                      <Bookmark className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}

            {/* Streaming message */}
            {isStreaming && streamingSessionId === currentSessionId && streamingText && (
              <div className="animate-message-in flex flex-col items-start">
                <div className="flex gap-3">
                  <div className="shrink-0 mt-0.5">
                    <RobotAvatar size={48} avatarId={assistantSettings.avatarId} avatarUrl={assistantSettings.avatarUrl} />
                  </div>
                  <div className="max-w-[80%]">
                    <div className="flex items-baseline gap-1.5 mb-0.5 px-1">
                      <span className="text-[12px] font-medium text-gray-600">{assistantSettings.name}</span>
                    </div>
                    <div className="rounded-2xl rounded-bl-md px-4 py-3 text-[14px] leading-relaxed bg-gray-100 text-gray-800 break-words">
                      <StreamingMarkdown content={streamingText} />
                      <span className="inline-block w-0.5 h-4 bg-blue-500 animate-pulse ml-0.5 align-text-bottom" />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Streaming loading indicator */}
            {isStreaming && streamingSessionId === currentSessionId && !streamingText && (
              <div className="animate-message-in flex flex-col items-start">
                <div className="flex gap-3">
                  <div className="shrink-0 mt-0.5">
                    <RobotAvatar size={48} avatarId={assistantSettings.avatarId} avatarUrl={assistantSettings.avatarUrl} />
                  </div>
                  <div>
                    <div className="flex items-baseline gap-1.5 mb-0.5 px-1">
                      <span className="text-[12px] font-medium text-gray-600">{assistantSettings.name}</span>
                    </div>
                    <div className="rounded-2xl rounded-bl-md px-4 py-3 bg-gray-100 text-gray-500 flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm">
                        {currentModelInfo?.name} 正在思考...
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Restored streaming text from interrupted session (user navigated away mid-stream) */}
            {!isStreaming && currentSession?._streamingText && (
              <div className="animate-message-in flex flex-col items-start">
                <div className="flex gap-3">
                  <div className="shrink-0 mt-0.5">
                    <RobotAvatar size={48} avatarId={assistantSettings.avatarId} avatarUrl={assistantSettings.avatarUrl} />
                  </div>
                  <div className="max-w-[80%]">
                    <div className="flex items-baseline gap-1.5 mb-0.5 px-1">
                      <span className="text-[12px] font-medium text-gray-600">{assistantSettings.name}</span>
                      <span className="text-[10px] text-amber-500">输出中断 · 已恢复</span>
                    </div>
                    <div className="rounded-2xl rounded-bl-md px-4 py-3 text-[14px] leading-relaxed bg-amber-50 text-gray-800 break-words border border-amber-200">
                      <StreamingMarkdown content={currentSession._streamingText!} />
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Input Area - Coze-style */}
        <div className="px-3 pb-3 pt-2 sm:px-5 sm:pb-4 shrink-0">
          {/* Quote Card */}
          {quotedMessage && (
            <div className="mb-2 rounded-xl border border-blue-200/60 bg-blue-50/50 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2 min-w-0">
                  <div className="mt-0.5 h-5 w-1 shrink-0 rounded-full bg-blue-400" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 text-xs text-blue-600 mb-0.5">
                      <span className="font-medium">{quotedMessage.role === 'ai' ? assistantSettings.name : '你'}</span>
                      <span>·</span>
                      <span>引用</span>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">{quotedMessage.content}</p>
                  </div>
                </div>
                <button
                  onClick={() => setQuotedMessage(null)}
                  className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>
          )}
          {/* Attached Files */}
          {fileCardVisible && attachedFiles.length > 0 && (
            <div className="mb-2 rounded-xl border border-border/60 bg-white p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">已添加 {attachedFiles.length} 个文件</span>
                <button
                  onClick={clearAttachedFiles}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  全部清除
                </button>
              </div>
              {attachedFiles.map((f, idx) => (
                <div key={`${f.name}-${idx}`} className="flex items-center justify-between rounded-lg border border-border/40 px-3 py-2 bg-muted/20">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 text-blue-500 shrink-0" />
                    <span className="text-sm font-medium truncate">{f.name}</span>
                    <span className="text-xs text-muted-foreground shrink-0">{f.size}</span>
                  </div>
                  <button
                    onClick={() => removeAttachedFile(idx)}
                    className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground shrink-0"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Chat Input Card */}
          <div className="rounded-2xl border border-border/60 bg-white shadow-sm overflow-hidden">
            {/* Textarea */}
            <textarea
              ref={(el) => {
                if (el) {
                  el.style.height = 'auto';
                  const lineHeight = 24;
                  const paddingY = 16;
                  const minH = lineHeight * 1 + paddingY;
                  const maxH = lineHeight * 8 + paddingY;
                  el.style.height = `${Math.min(Math.max(el.scrollHeight, minH), maxH)}px`;
                }
              }}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={`向 ${currentModelInfo?.name || 'AI'} 提问...`}
              disabled={isStreaming}
              rows={1}
              className="w-full resize-none border-0 bg-transparent px-3 pt-2.5 pb-1 text-sm leading-6 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-0 sm:px-4 sm:pt-3"
            />

            {/* Bottom Toolbar */}
            <div className="flex items-center justify-between px-2 pb-2 pt-0.5 sm:px-3 sm:pb-2.5">
              {/* Left: + Upload + Model Selector */}
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  title="上传文件 (CSV/Excel/Parquet)"
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  <Plus className="h-5 w-5" />
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".csv,.xlsx,.xls,.parquet,.json,.txt"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files.length > 0) {
                      handleFilesSelected(e.target.files);
                      e.target.value = '';
                    }
                  }}
                />

                <ModelSelector config={modelConfig} onConfigChange={setModelConfig} />

                {/* Quick Commands - "..." button */}
                <Popover open={quickCmdOpen} onOpenChange={setQuickCmdOpen}>
                  <PopoverTrigger asChild>
                    <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                      <MoreHorizontal className="h-4 w-4" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent
                    side="top"
                    align="start"
                    className="w-72 p-2 z-50"
                    sideOffset={8}
                  >
                    <div className="mb-1.5 px-1 text-xs font-medium text-muted-foreground">快捷指令</div>
                    <div className="space-y-0.5">
                      {quickActions.map((action) => (
                        <button
                          key={action.label}
                          onClick={() => {
                            setInputValue(action.keyword);
                            setQuickCmdOpen(false);
                          }}
                          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-foreground transition-colors hover:bg-accent"
                        >
                          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600">
                            <action.icon className="h-3.5 w-3.5" />
                          </div>
                          <span>{action.label}</span>
                        </button>
                      ))}
                    </div>
                  </PopoverContent>
                </Popover>
              </div>

              {/* Right: Mic + Send/Stop */}
              <div className="flex items-center gap-1">
                <TooltipProvider delayDuration={200}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                        <Mic className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">
                      语音输入
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>

                {isStreaming ? (
                  <button
                    onClick={handleStopStream}
                    className="flex h-8 w-8 items-center justify-center rounded-lg bg-destructive text-white transition-colors hover:bg-destructive/90"
                  >
                    <X className="h-4 w-4" />
                  </button>
                ) : (
                  <button
                    onClick={() => handleSend()}
                    disabled={!inputValue.trim() && attachedFiles.length === 0}
                    className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm transition-all hover:from-blue-700 hover:to-indigo-700 disabled:opacity-40 disabled:shadow-none"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </div>


        </div>
      </div>

      {/* Right Panel - responsive: hidden on small screens unless explicitly opened */}
      {rightPanelOpen && (
        <div className="flex w-[300px] shrink-0 flex-col border-l border-border/60 bg-white overflow-hidden max-lg:fixed max-lg:right-0 max-lg:top-[56px] max-lg:bottom-0 max-lg:z-40 max-lg:shadow-xl max-lg:animate-in max-lg:slide-in-from-right-2 max-lg:duration-200">
          {/* Mobile close button */}
          <button onClick={() => setRightPanelOpen(false)} className="lg:hidden flex items-center gap-1.5 px-3 py-2 text-xs text-muted-foreground hover:text-foreground border-b border-border/40">
            <X className="h-3.5 w-3.5" /> 收起面板
          </button>
          <div className="flex-1 overflow-y-auto">
            <div className="p-3 space-y-3">
              {/* Agent Workflow Pipeline */}
              <Card className="border-border/60">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold">Agent 工作流</h3>
                    <div className="flex items-center gap-1">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                      </span>
                      <span className="text-[10px] text-emerald-600 font-medium">运行中</span>
                    </div>
                  </div>

                  {/* Version Tabs */}
                  <div className="mb-3">
                    <div className="flex items-center gap-1 flex-wrap">
                      {workflowVersions.length > 1 && workflowVersions.map((v, i) => {
                        const completedCount = v.steps.filter((s) => s.status === 'completed').length;
                        const allDone = completedCount === v.steps.length;
                        const isActive = i === activeVersionIdx;
                        return (
                          <button
                            key={v.version}
                            onClick={() => setActiveVersionIdx(i)}
                            className={cn(
                              "flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-all",
                              isActive
                                ? "bg-primary/10 text-primary ring-1 ring-primary/20"
                                : "bg-muted/50 text-muted-foreground hover:bg-muted",
                              allDone && !isActive && "bg-emerald-50 text-emerald-600",
                            )}
                          >
                            <span className="font-mono">{v.version}</span>
                            <span className="text-[9px] opacity-60">{completedCount}/{v.steps.length}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Workflow Steps */}
                  <div className="space-y-0">
                    {agentSteps.map((step, i) => {
                      const isActive = step.status === 'running';
                      const isCompleted = step.status === 'completed';
                      const isLast = i === agentSteps.length - 1;
                      return (
                        <div key={step.id}>
                          <div className="flex items-start gap-2.5">
                            <div className="flex flex-col items-center">
                              <div className={cn(
                                "flex items-center justify-center w-6 h-6 rounded-full shrink-0 transition-all duration-300",
                                isCompleted && "bg-emerald-500 text-white",
                                isActive && "bg-blue-500 text-white ring-2 ring-blue-200",
                                !isCompleted && !isActive && "bg-gray-100 text-gray-400"
                              )}>
                                {isCompleted ? (
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                ) : isActive ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <span className="text-[10px] font-bold">{i + 1}</span>
                                )}
                              </div>
                              {!isLast && (
                                <div className={cn(
                                  "w-0.5 h-6 transition-colors duration-300",
                                  isCompleted && "bg-emerald-300",
                                  isActive && "bg-blue-200",
                                  !isCompleted && !isActive && "bg-gray-200"
                                )} />
                              )}
                            </div>
                            <div className="flex-1 min-w-0 pb-2">
                              <div className="flex items-center justify-between">
                                <span className={cn(
                                  "text-xs font-medium",
                                  isCompleted && "text-emerald-700",
                                  isActive && "text-blue-700",
                                  !isCompleted && !isActive && "text-gray-400"
                                )}>
                                  {step.name}
                                </span>
                                {step.duration && isCompleted && (
                                  <span className="text-[10px] text-gray-400">{step.duration}</span>
                                )}
                              </div>
                              {isActive && step.detail && (
                                <p className="text-[10px] text-blue-500 mt-0.5 animate-pulse">{step.detail}</p>
                              )}
                              {isCompleted && step.output && (
                                <p className="text-[10px] text-emerald-500 mt-0.5">{step.output}</p>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Repo & Deploy Status Indicators */}
                  {workflowVersions[activeVersionIdx] && (
                    <div className="mt-3 pt-3 border-t border-border/40 flex gap-2">
                      <div className={cn(
                        "flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium",
                        workflowVersions[activeVersionIdx].repoStatus === '已入库'
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-gray-50 text-gray-400"
                      )}>
                        <Archive className="h-3 w-3" />
                        {workflowVersions[activeVersionIdx].repoStatus}
                      </div>
                      <div className={cn(
                        "flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium",
                        workflowVersions[activeVersionIdx].deployStatus === '已部署'
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-gray-50 text-gray-400"
                      )}>
                        <Server className="h-3 w-3" />
                        {workflowVersions[activeVersionIdx].deployStatus}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Modeling Task Card */}
              <Card className="border-border/60">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-bold">建模任务</h3>
                    <div className="flex items-center gap-2">
                      {panelData.taskId ? (
                        <Link to={`/tasks?highlight=${panelData.taskId}`} className="text-[11px] text-blue-600 hover:text-blue-800 transition-colors flex items-center gap-0.5">
                          查看任务 <ExternalLink className="h-3 w-3" />
                        </Link>
                      ) : null}
                      <Link to="/tasks" className="text-[11px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-0.5">
                        全部任务 <ExternalLink className="h-3 w-3" />
                      </Link>
                    </div>
                  </div>
                  {(() => {
                    if (panelData.taskStatus === 'pending') {
                      return (
                        <div className="text-xs text-muted-foreground py-2">
                          暂无关联任务，对话开始后将自动创建
                        </div>
                      );
                    }
                    const completedSteps = agentSteps.filter((s) => s.status === 'completed').length;
                    return (
                      <div className="space-y-0">
                        <div className="flex items-center justify-between border-b border-border/40 py-2">
                          <span className="text-sm text-muted-foreground">任务名称</span>
                          <span className="text-sm font-medium truncate max-w-[140px]">{panelData.taskName}</span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/40 py-2">
                          <span className="text-sm text-muted-foreground">状态</span>
                          <Badge variant="outline" className={
                            panelData.taskStatus === 'running' ? 'bg-blue-100 text-blue-700 border-blue-200 text-[10px]' :
                            panelData.taskStatus === 'completed' ? 'bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px]' :
                            'bg-gray-100 text-gray-500 border-gray-200 text-[10px]'
                          }>
                            {panelData.taskStatus === 'running' ? '进行中' : '已完成'}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/40 py-2">
                          <span className="text-sm text-muted-foreground">数据文件</span>
                          <span className="text-sm font-bold transition-all duration-300">{panelData.dataFileCount} 个</span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/40 py-2">
                          <span className="text-sm text-muted-foreground">模型产物</span>
                          <span className="text-sm font-bold transition-all duration-300">{panelData.modelFileCount} 个</span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/40 py-2">
                          <span className="text-sm text-muted-foreground">有效特征</span>
                          <span className="text-sm font-bold transition-all duration-300">{panelData.featureCount > 0 ? `${panelData.featureCount} 个` : '暂无'}</span>
                        </div>
                        <div className="flex items-center justify-between py-2">
                          <span className="text-sm text-muted-foreground">入库状态</span>
                          {workflowVersions[activeVersionIdx]?.repoStatus === '已入库' ? (
                            <Badge className="bg-emerald-50 text-emerald-600 border-emerald-200 text-[10px]">
                              <Package className="h-2.5 w-2.5 mr-0.5" /> 已入库
                            </Badge>
                          ) : (
                            <span className="text-sm text-muted-foreground">未入库</span>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </CardContent>
              </Card>

              {/* Model Info */}
              <Card className="border-border/60">
                <CardContent className="p-4">
                  <h3 className="text-sm font-bold">当前模型</h3>
                  <div className="mt-2 space-y-0">
                    <div className="flex items-center justify-between border-b border-border/40 py-2">
                      <span className="text-sm text-muted-foreground">模型</span>
                      <span className="text-sm font-bold">{currentModelInfo?.name}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-border/40 py-2">
                      <span className="text-sm text-muted-foreground">生成随机性</span>
                      <span className="text-sm font-bold">{modelConfig.temperature.toFixed(1)}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-border/40 py-2">
                      <span className="text-sm text-muted-foreground">重复语句惩罚</span>
                      <span className="text-sm font-bold">{modelConfig.frequencyPenalty.toFixed(1)}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-border/40 py-2">
                      <span className="text-sm text-muted-foreground">Top P</span>
                      <span className="text-sm font-bold">{modelConfig.topP.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-border/40 py-2">
                      <span className="text-sm text-muted-foreground">最大回复长度</span>
                      <span className="text-sm font-bold">{modelConfig.maxTokens}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-border/40 py-2">
                      <span className="text-sm text-muted-foreground">深度思考</span>
                      <span className="text-sm font-bold">{modelConfig.thinking ? `已启用(${modelConfig.thinkingLevel === 'low' ? '低' : modelConfig.thinkingLevel === 'medium' ? '中' : '高'})` : '已关闭'}</span>
                    </div>
                    <div className="flex items-center justify-between py-2">
                      <span className="text-sm text-muted-foreground">输出格式</span>
                      <span className="text-sm font-bold">{modelConfig.outputFormat === 'json' ? 'JSON' : modelConfig.outputFormat === 'text' ? '纯文本' : 'Markdown'}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Data Overview - Dynamic panel driven by conversation progress */}
              <Card className="border-border/60">
                <CardContent className="p-4">
                  <h3 className="text-sm font-bold">数据概览</h3>
                  {panelData.dataFileCount === 0 ? (
                    <div className="text-xs text-muted-foreground py-2">
                      对话开始后自动展示数据概览
                    </div>
                  ) : (
                    <div className="mt-2 space-y-0">
                      <div className="flex items-center justify-between border-b border-border/40 py-2">
                        <span className="text-sm text-muted-foreground">数据文件</span>
                        <span className="text-sm font-bold transition-all duration-300">{panelData.dataFileCount} 个</span>
                      </div>
                      <div className="flex items-center justify-between border-b border-border/40 py-2">
                        <span className="text-sm text-muted-foreground">数据总量</span>
                        <span className="text-sm font-bold transition-all duration-300">{panelData.sampleCount > 0 ? panelData.sampleCount.toLocaleString() + ' 条' : '暂无'}</span>
                      </div>
                      <div className="flex items-center justify-between border-b border-border/40 py-2">
                        <span className="text-sm text-muted-foreground">数据大小</span>
                        <span className="text-sm font-bold transition-all duration-300">{panelData.dataSizeLabel}</span>
                      </div>
                      <div className="flex items-center justify-between border-b border-border/40 py-2">
                        <span className="text-sm text-muted-foreground">模型产物</span>
                        <span className="text-sm font-bold transition-all duration-300">{panelData.modelFileCount} 个</span>
                      </div>
                      <div className="flex items-center justify-between py-2">
                        <span className="text-sm text-muted-foreground">有效特征</span>
                        <span className="text-sm font-bold transition-all duration-300">{panelData.featureCount > 0 ? `${panelData.featureCount} 个` : '暂无'}</span>
                      </div>
                      {panelData.metrics && (
                        <div className="pt-2 mt-2 border-t border-border/40">
                          <div className="text-[10px] text-muted-foreground mb-1.5">模型指标</div>
                          <div className="grid grid-cols-3 gap-2">
                            <div className="text-center">
                              <div className="text-sm font-bold text-blue-600">{panelData.metrics.auc.toFixed(3)}</div>
                              <div className="text-[10px] text-muted-foreground">AUC</div>
                            </div>
                            <div className="text-center">
                              <div className="text-sm font-bold text-emerald-600">{panelData.metrics.ks.toFixed(2)}</div>
                              <div className="text-[10px] text-muted-foreground">KS</div>
                            </div>
                            <div className="text-center">
                              <div className="text-sm font-bold text-amber-600">{panelData.metrics.psi.toFixed(2)}</div>
                              <div className="text-[10px] text-muted-foreground">PSI</div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Compute Load Panel */}
              <Card className="border-border/60 overflow-hidden">
                <CardContent className="p-0">
                  <div className="rounded-lg bg-gray-900 p-4 text-white">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-blue-400" />
                        <h3 className="text-sm font-bold">算力负载</h3>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-gray-300">混合编排</span>
                    </div>
                    <div className="rounded-lg bg-white/5 px-3 py-3 text-xs text-gray-300">
                      当前后端没有提供实时集群/GPU/CPU/MEM 监控接口，因此不再展示演示负载数值。
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Precision Climb Tracker */}
              {(driftAlert || precisionClimbDone) && (
                <Card className={cn(
                  'border transition-all duration-500 overflow-hidden',
                  precisionClimbDone
                    ? 'border-emerald-200 shadow-[0_8px_24px_rgba(16,185,129,0.15)]'
                    : 'border-blue-200'
                )}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Activity className={cn('h-4 w-4', precisionClimbDone ? 'text-emerald-500' : 'text-blue-500')} />
                        <h3 className="text-sm font-bold">模型达标追踪</h3>
                      </div>
                      <span className={cn(
                        'text-[10px] px-2 py-0.5 rounded-full font-medium',
                        precisionClimbDone
                          ? 'bg-emerald-50 text-emerald-600'
                          : 'bg-blue-50 text-blue-600'
                      )}>
                        {precisionClimbDone ? '达标' : '修复中'}
                      </span>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-3">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1">Current Precision</p>
                      <p className={cn(
                        'font-mono text-3xl font-bold transition-colors duration-300',
                        precisionClimbDone ? 'text-emerald-600' : 'text-gray-900'
                      )}>
                        {precisionClimb.toFixed(3)}
                      </p>
                      {/* Progress bar */}
                      <div className="mt-3 h-2 rounded-full bg-gray-200">
                        <div
                          className={cn(
                            'h-2 rounded-full transition-all duration-300',
                            precisionClimbDone ? 'bg-emerald-500' : 'bg-blue-500'
                          )}
                          style={{ width: `${42 + ((precisionClimb - 0.82) / (0.962 - 0.82)) * 50}%` }}
                        />
                      </div>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {precisionClimbDone
                          ? 'Precision 已抬升至 0.962，满足银行准入线'
                          : '正在重训练修复线上漂移...'}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Session Actions */}
              <Card className="border-border/60">
                <CardContent className="p-4 space-y-2">
                  <h3 className="text-sm font-bold">会话操作</h3>
                  <Link to="/service">
                    <Button className="w-full gap-2 justify-start bg-gradient-to-r from-blue-600 to-indigo-600 shadow-md shadow-blue-500/20 hover:from-blue-700 hover:to-indigo-700">
                      <Rocket className="h-4 w-4" /> 部署到模型服务
                    </Button>
                  </Link>
                  <Button variant="outline" className="w-full gap-2 justify-start" onClick={() => { toast.success('会话报告已导出'); }}>
                    <Download className="h-4 w-4" /> 导出当前会话报告
                  </Button>
                  <Button variant="outline" className="w-full gap-2 justify-start text-destructive hover:bg-destructive/10" onClick={() => {
                    setSessions((prev) =>
                      prev.map((s) => {
                        if (s.id !== currentSessionId) return s;
                        return {
                          ...s,
                          status: '待开始',
                          progress: '等待输入',
                          messages: [
                            { role: 'ai' as const, text: '会话已清空，请输入你的建模目标或上传数据，我将引导你完成全流程建模。', thinking: { steps: [{ label: '等待用户输入', detail: '等待用户输入建模需求' }], duration: '0.1s' } },
                          ],
                        };
                      })
                    );
                    toast.success('会话已清空');
                  }}>
                    <Trash2 className="h-4 w-4" /> 清空当前会话
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}
      {/* Assistant Settings Dialog */}
      <Dialog open={showAssistantSettings} onOpenChange={setShowAssistantSettings}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>助手设置</DialogTitle>
            <DialogDescription>
              自定义 AI 助手的名称、性格和提示词，仅影响聊天风格和语气，不改变建模核心功能。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-5 py-2">
            {/* Avatar Upload */}
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">助手头像</Label>
              <div className="flex items-center gap-4">
                <div className="relative group">
                  <RobotAvatar size={56} avatarId={tempAssistantSettings.avatarId} avatarUrl={tempAssistantSettings.avatarUrl} />
                  <label className="absolute inset-0 flex items-center justify-center rounded-full bg-black/0 group-hover:bg-black/40 transition-colors cursor-pointer">
                    <Camera className="h-5 w-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          const reader = new FileReader();
                          reader.onload = (ev) => {
                            const dataUrl = ev.target?.result as string;
                            setTempAssistantSettings((s) => ({ ...s, avatarUrl: dataUrl }));
                          };
                          reader.readAsDataURL(file);
                        }
                      }}
                    />
                  </label>
                </div>
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground">点击头像上传图片</p>
                  <p className="text-[10px] text-muted-foreground/60 mt-0.5">支持 JPG、PNG、GIF，建议正方形</p>
                  {tempAssistantSettings.avatarUrl && (
                    <button
                      onClick={() => setTempAssistantSettings((s) => ({ ...s, avatarUrl: '' }))}
                      className="text-[10px] text-red-500 hover:text-red-600 mt-1"
                    >
                      移除自定义头像
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Name */}
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-muted-foreground">助手名称</Label>
              <Input
                value={tempAssistantSettings.name}
                onChange={(e) => setTempAssistantSettings((s) => ({ ...s, name: e.target.value }))}
                className="h-9"
                placeholder="输入助手名称"
              />
            </div>

            {/* Personality */}
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">性格风格</Label>
              <div className="grid grid-cols-2 gap-2">
                {PERSONALITIES.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => setTempAssistantSettings((s) => ({ ...s, personality: p.value }))}
                    className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                      tempAssistantSettings.personality === p.value
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-border/60 hover:border-blue-300 hover:bg-blue-50/50'
                    }`}
                  >
                    <div className="text-sm font-medium">{p.label}</div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground leading-snug">{p.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Custom Prompt */}
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-muted-foreground">自定义提示词（可选）</Label>
              <Textarea
                value={tempAssistantSettings.customPrompt}
                onChange={(e) => setTempAssistantSettings((s) => ({ ...s, customPrompt: e.target.value }))}
                className="min-h-[80px] resize-none text-sm"
                placeholder="例：请用通俗易懂的语言解释专业术语，多用类比和案例..."
              />
              <p className="text-[11px] text-muted-foreground">
                自定义提示词会追加到系统提示词末尾，用于微调助手的聊天风格，不影响建模专业能力。
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowAssistantSettings(false)}
            >
              取消
            </Button>
            <Button
              onClick={() => {
                setAssistantSettings(tempAssistantSettings);
                setShowAssistantSettings(false);
              }}
            >
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>


    </div>
  );
}
