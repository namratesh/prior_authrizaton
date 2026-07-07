import type { ReactElement } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import PatientPortal from "./pages/PatientPortal";
import ReviewerPortal from "./pages/ReviewerPortal";
import AdminPortal from "./pages/AdminPortal";
import Login from "./pages/Login";
import NavBar from "@/components/layout/NavBar";
import BackgroundDecor from "@/components/layout/BackgroundDecor";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getAuth, type Role } from "./store/auth";

const ROLE_HOME: Record<Role, string> = {
  patient: "/patient",
  reviewer: "/reviewer",
  admin: "/admin",
};

function ProtectedLayout({
  children,
  allow,
}: {
  children: ReactElement;
  allow: Role;
}) {
  const auth = getAuth();
  const location = useLocation();
  if (!auth) return <Navigate to="/login" replace />;
  // Each portal is scoped to its own role — a logged-in Patient must not be
  // able to reach the Reviewer/Admin views (and vice versa) by URL alone.
  if (auth.role !== allow) return <Navigate to={ROLE_HOME[auth.role]} replace />;
  return (
    <div
      data-role={auth.role}
      className="relative flex min-h-screen flex-col gradient-mesh-bg font-sans text-foreground"
    >
      <BackgroundDecor />
      <NavBar />
      <AnimatePresence mode="wait">
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="flex-1"
        >
          {children}
        </motion.main>
      </AnimatePresence>
      <Toaster />
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <TooltipProvider delayDuration={150}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedLayout allow="patient"><PatientPortal /></ProtectedLayout>} />
          <Route path="/patient" element={<ProtectedLayout allow="patient"><PatientPortal /></ProtectedLayout>} />
          <Route path="/reviewer" element={<ProtectedLayout allow="reviewer"><ReviewerPortal /></ProtectedLayout>} />
          <Route path="/reviewer/:caseId" element={<ProtectedLayout allow="reviewer"><ReviewerPortal /></ProtectedLayout>} />
          <Route path="/admin" element={<ProtectedLayout allow="admin"><AdminPortal /></ProtectedLayout>} />
        </Routes>
      </TooltipProvider>
    </BrowserRouter>
  );
}

export default App;
