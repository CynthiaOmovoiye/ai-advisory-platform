"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ClipboardList,
  FileStack,
  Users,
  GaugeCircle,
  FlaskConical,
  LogOut,
  ChevronDown,
  Sparkles,
} from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string; icon: React.ComponentType<{ className?: string }>; need: "any" | "manage" | "admin" };

const NAV: NavItem[] = [
  { href: "/assessments", label: "Assessments", icon: ClipboardList, need: "any" },
  { href: "/templates", label: "Templates", icon: FileStack, need: "manage" },
  { href: "/members", label: "Members", icon: Users, need: "manage" },
  { href: "/admin", label: "Admin", icon: GaugeCircle, need: "admin" },
  { href: "/eval", label: "Evaluation", icon: FlaskConical, need: "admin" },
];

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground">
        <Sparkles className="size-4" />
      </span>
      <span>AI Advisory</span>
    </Link>
  );
}

export function SiteHeader() {
  const { data: session, status, update } = useSession();
  const pathname = usePathname();

  const roles = new Set([
    ...(session?.globalRoles ?? []),
    ...((session?.org && session?.orgRoles?.[session.org]) || []),
  ]);
  const isAdmin = roles.has("admin");
  const canManage = isAdmin || roles.has("consultant");
  const authed = status === "authenticated" && !!session?.user;

  const visible = NAV.filter((n) =>
    n.need === "any" ? true : n.need === "manage" ? canManage : isAdmin,
  );

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Brand />

        {authed && (
          <nav className="hidden items-center gap-1 md:flex">
            {visible.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + "/");
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                  )}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        )}

        <div className="ml-auto flex items-center gap-2">
          {!authed ? (
            <>
              <Link href="/login" className={buttonVariants({ variant: "ghost", size: "sm" })}>
                Sign in
              </Link>
              <Link href="/signup" className={buttonVariants({ size: "sm" })}>
                Sign up
              </Link>
            </>
          ) : (
            <>
              {session.memberships && session.memberships.length > 1 && (
                <select
                  value={session.org}
                  onChange={(e) => void update({ org: e.target.value })}
                  aria-label="Active organization"
                  className="hidden h-8 rounded-md border border-input bg-background px-2 text-sm text-muted-foreground sm:block"
                >
                  {session.memberships.map((m) => (
                    <option key={m.organization_id} value={m.organization_id}>
                      {m.organization_name}
                    </option>
                  ))}
                </select>
              )}
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button variant="outline" size="sm" className="gap-1.5">
                      <span className="grid size-5 place-items-center rounded-full bg-primary/10 text-[10px] font-semibold text-primary">
                        {(session.user.email ?? "?").slice(0, 1).toUpperCase()}
                      </span>
                      <span className="hidden max-w-[12ch] truncate sm:inline">{session.user.email}</span>
                      <ChevronDown className="size-3.5 opacity-60" />
                    </Button>
                  }
                />
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
                    {session.user.email}
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {session.memberships && session.memberships.length > 1 && (
                    <DropdownMenuLabel className="text-xs font-normal text-muted-foreground sm:hidden">
                      {session.memberships.find((m) => m.organization_id === session.org)?.organization_name}
                    </DropdownMenuLabel>
                  )}
                  <DropdownMenuItem onClick={() => void signOut({ callbackUrl: "/login" })}>
                    <LogOut className="size-4" />
                    Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
