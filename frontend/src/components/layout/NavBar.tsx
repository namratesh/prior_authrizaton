import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  HeartPulse,
  User,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  ChevronDown,
} from "lucide-react";
import { getAuth, logout, ROLE_CREDENTIALS, type Role } from "@/store/auth";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

const NAV_LINKS: Record<Role, { to: string; label: string; icon: typeof User }> = {
  patient: { to: "/patient", label: "Patient Portal", icon: User },
  reviewer: { to: "/reviewer", label: "Reviewer Portal", icon: ClipboardCheck },
  admin: { to: "/admin", label: "Admin Portal", icon: LayoutDashboard },
};

export default function NavBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const auth = getAuth();
  const initials = auth ? ROLE_CREDENTIALS[auth.role].label.slice(0, 2).toUpperCase() : "";
  // Each role is scoped to exactly one portal (see App.tsx's route gating) —
  // show only that role's own link rather than all three.
  const ownLink = auth ? NAV_LINKS[auth.role] : null;

  return (
    <nav className="sticky top-0 z-40 border-b border-white/10 bg-navy-900/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-2 px-6">
        <Link to={ownLink?.to ?? "/login"} className="mr-6 flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[linear-gradient(135deg,#e00000,#ff4d4d)] shadow-glow">
            <HeartPulse className="text-white" size={20} />
          </span>
          <span className="font-display text-lg font-bold tracking-tight text-white">
            Agentic<span className="text-teal-300">PA</span>
          </span>
        </Link>

        {ownLink && (
          <div className="flex items-center gap-1">
            {(() => {
              const { to, label, icon: Icon } = ownLink;
              const active = location.pathname.startsWith(to);
              return (
                <Link
                  to={to}
                  className={cn(
                    "relative flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                    active ? "text-white" : "text-white/60 hover:text-white"
                  )}
                >
                  {active && (
                    <motion.span
                      layoutId="nav-pill"
                      className="nav-pill absolute inset-0 rounded-lg bg-white/10 ring-1 ring-inset ring-white/15"
                      transition={{ type: "spring", stiffness: 400, damping: 32 }}
                    />
                  )}
                  <Icon size={16} className="relative z-10" />
                  <span className="relative z-10">{label}</span>
                </Link>
              );
            })()}
          </div>
        )}

        {/* DEMO-MOCKED: single hardcoded login gate stands in for real auth. */}
        {auth && (
          <div className="ml-auto">
            <DropdownMenu>
              <DropdownMenuTrigger className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2.5 text-sm text-white/80 outline-none transition-colors hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-teal-300">
                <Avatar className="h-8 w-8">
                  <AvatarFallback>{initials}</AvatarFallback>
                </Avatar>
                <span className="hidden font-medium sm:inline">
                  {ROLE_CREDENTIALS[auth.role].label}
                </span>
                <ChevronDown size={14} className="opacity-70" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>
                  Signed in as {ROLE_CREDENTIALS[auth.role].label}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-radiant focus:bg-red-50 focus:text-radiant"
                  onClick={() => {
                    logout();
                    navigate("/login");
                  }}
                >
                  <LogOut size={16} />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
      </div>
    </nav>
  );
}
