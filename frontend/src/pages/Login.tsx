import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  HeartPulse,
  User,
  ClipboardCheck,
  LayoutDashboard,
  Lock,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { login, ROLE_CREDENTIALS, type Role } from "../store/auth";
import BackgroundDecor from "@/components/layout/BackgroundDecor";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const ROLE_TABS: { role: Role; icon: typeof User; path: string }[] = [
  { role: "patient", icon: User, path: "/patient" },
  { role: "reviewer", icon: ClipboardCheck, path: "/reviewer" },
  { role: "admin", icon: LayoutDashboard, path: "/admin" },
];

const FEATURES = [
  { icon: Workflow, title: "Multi-agent adjudication", desc: "Intake, cost, and policy agents run in parallel on every request." },
  { icon: ShieldCheck, title: "Human-in-the-loop", desc: "Deterministic hard-gates escalate the right cases to a reviewer." },
  { icon: Sparkles, title: "Self-improving", desc: "Reviewer corrections feed forward as few-shot guidance on new cases." },
];

// Animated abstract "connected nodes" SVG — the multi-agent visual motif.
function ConnectedNodes() {
  const nodes = [
    { cx: 60, cy: 70 }, { cx: 210, cy: 40 }, { cx: 330, cy: 110 },
    { cx: 130, cy: 180 }, { cx: 280, cy: 210 }, { cx: 80, cy: 280 },
    { cx: 340, cy: 300 }, { cx: 200, cy: 320 },
  ];
  const edges = [[0, 1], [1, 2], [0, 3], [3, 4], [1, 4], [3, 5], [4, 7], [5, 7], [4, 6], [7, 6]];
  return (
    <svg viewBox="0 0 400 360" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#5fd4bd" />
          <stop offset="100%" stopColor="#7f9cce" />
        </linearGradient>
      </defs>
      {edges.map(([a, b], i) => (
        <motion.line
          key={i}
          x1={nodes[a].cx} y1={nodes[a].cy} x2={nodes[b].cx} y2={nodes[b].cy}
          stroke="url(#edge)" strokeWidth={1.5} strokeOpacity={0.5}
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 0.5 }}
          transition={{ duration: 1.2, delay: 0.3 + i * 0.08 }}
        />
      ))}
      {nodes.map((n, i) => (
        <motion.circle
          key={i}
          cx={n.cx} cy={n.cy} r={i % 3 === 0 ? 7 : 5}
          fill={i % 3 === 0 ? "#5fd4bd" : "#adc1e0"}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: [1, 1.25, 1], opacity: 1 }}
          transition={{ scale: { duration: 2.4, repeat: Infinity, delay: i * 0.25 }, opacity: { duration: 0.6, delay: i * 0.1 } }}
        />
      ))}
    </svg>
  );
}

// DEMO-MOCKED: single login gate for the whole app; hardcoded creds per role
// (see store/auth.ts). Not a real auth/session backend — see CLAUDE.md scope.
export default function Login() {
  const navigate = useNavigate();
  const [role, setRole] = useState<Role>("patient");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [shake, setShake] = useState(0);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (login(role, username, password)) {
      const tab = ROLE_TABS.find((t) => t.role === role)!;
      navigate(tab.path);
    } else {
      setError("Incorrect username or password for this role.");
      setShake((s) => s + 1);
    }
  }

  return (
    <div className="relative grid min-h-screen gradient-mesh-bg font-sans text-foreground lg:grid-cols-2">
      <BackgroundDecor intense />

      {/* Left — brand / motif panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-navy-900/90 p-12 text-white lg:flex">
        <div className="flex items-center gap-2">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-[linear-gradient(135deg,#e00000,#ff4d4d)] shadow-glow">
            <HeartPulse size={22} />
          </span>
          <span className="font-display text-xl font-bold tracking-tight">
            Agentic<span className="text-teal-300">PA</span>
          </span>
        </div>

        <div className="relative">
          <div className="pointer-events-none absolute inset-0 mx-auto max-w-md opacity-90">
            <ConnectedNodes />
          </div>
          <div className="relative mt-40 max-w-md">
            <h1 className="font-display text-4xl font-bold leading-tight">
              Prior authorization,<br />
              <span
                style={{
                  background: "linear-gradient(120deg,#5fd4bd,#adc1e0)",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  color: "transparent",
                }}
              >
                reasoned by agents.
              </span>
            </h1>
            <p className="mt-4 text-white/70">
              Clinical RAG, financial benchmarking, and human oversight — working together on
              every AARP Medicare request.
            </p>
          </div>
        </div>

        <div className="relative space-y-4">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="flex items-start gap-3">
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/10 ring-1 ring-white/15">
                <Icon size={16} className="text-teal-300" />
              </span>
              <div>
                <p className="text-sm font-medium">{title}</p>
                <p className="text-xs text-white/60">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right — login card */}
      <div className="flex items-center justify-center px-4 py-12">
        <motion.div
          key={shake}
          animate={shake ? { x: [0, -10, 10, -6, 6, 0] } : {}}
          transition={{ duration: 0.4 }}
          className="glass-card w-full max-w-md rounded-2xl p-8"
        >
          <div className="mb-6 flex items-center gap-2 lg:hidden">
            <HeartPulse className="text-radiant" size={24} />
            <span className="font-display text-xl font-bold">AgenticPA</span>
          </div>

          <h2 className="font-display text-2xl font-bold tracking-tight">Welcome back</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Select your role and sign in to continue.
          </p>

          <Tabs
            value={role}
            onValueChange={(v) => {
              setRole(v as Role);
              setError(null);
            }}
            className="mt-6"
          >
            <TabsList className="grid w-full grid-cols-3">
              {ROLE_TABS.map(({ role: r, icon: Icon }) => (
                <TabsTrigger key={r} value={r} className="flex-col gap-1 py-2 text-xs">
                  <Icon size={16} />
                  {ROLE_CREDENTIALS[r].label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={ROLE_CREDENTIALS[role].username}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={15} />
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pl-9"
                />
              </div>
            </div>

            {error && <p className="text-sm text-radiant">{error}</p>}

            <Button type="submit" variant="radiant" size="lg" className="w-full">
              Log in as {ROLE_CREDENTIALS[role].label}
            </Button>
          </form>

          <div className="mt-6 rounded-lg border border-border bg-muted/60 px-3 py-2 text-center text-xs text-muted-foreground">
            Demo credentials — <span className="font-medium text-foreground">{ROLE_CREDENTIALS[role].username}</span> / {ROLE_CREDENTIALS[role].password}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
