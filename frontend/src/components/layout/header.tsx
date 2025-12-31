"use client";

import * as React from "react";
import Link from "next/link";
import { Bell, Search, Plus, ChevronDown, LogOut, User, CreditCard } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { SearchInput } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";

interface HeaderProps {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function Header({ title, description, actions, className }: HeaderProps) {
  const [searchQuery, setSearchQuery] = React.useState("");

  return (
    <header
      className={cn(
        "h-16 flex items-center justify-between px-6 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-40",
        className
      )}
    >
      {/* Left side - Title or Search */}
      <div className="flex items-center gap-6">
        {title ? (
          <div>
            <h1 className="text-lg font-semibold">{title}</h1>
            {description && (
              <p className="text-sm text-muted-foreground">{description}</p>
            )}
          </div>
        ) : (
          <div className="w-80">
            <SearchInput
              placeholder="Search repositories, symbols, routes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onClear={() => setSearchQuery("")}
            />
          </div>
        )}
      </div>

      {/* Right side - Actions */}
      <div className="flex items-center gap-3">
        {/* Custom actions */}
        {actions}

        {/* Connect repo button */}
        <Button variant="glow" size="sm" asChild>
          <Link href="/repositories/connect">
            <Plus className="h-4 w-4 mr-1.5" />
            Connect Repo
          </Link>
        </Button>

        {/* Notifications */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-critical rounded-full" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80">
            <DropdownMenuLabel className="flex items-center justify-between">
              Notifications
              <Badge variant="secondary" size="sm">3 new</Badge>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <div className="max-h-80 overflow-y-auto">
              <NotificationItem
                title="PR Review Complete"
                description="Analysis of PR #142 found 2 critical issues"
                time="5m ago"
                severity="critical"
              />
              <NotificationItem
                title="Indexing Complete"
                description="laravel-app is now ready for queries"
                time="1h ago"
                severity="success"
              />
              <NotificationItem
                title="Usage Alert"
                description="You've used 80% of your monthly quota"
                time="2h ago"
                severity="warning"
              />
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="justify-center text-primary">
              View all notifications
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-2 pl-2 pr-3">
              <Avatar size="sm">
                <AvatarImage src="https://avatars.githubusercontent.com/u/1234567" />
                <AvatarFallback>JD</AvatarFallback>
              </Avatar>
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span>John Doe</span>
                <span className="text-xs font-normal text-muted-foreground">
                  john@example.com
                </span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <User className="h-4 w-4 mr-2" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem>
              <CreditCard className="h-4 w-4 mr-2" />
              Billing
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive focus:text-destructive">
              <LogOut className="h-4 w-4 mr-2" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

// Notification item component
interface NotificationItemProps {
  title: string;
  description: string;
  time: string;
  severity?: "critical" | "warning" | "success" | "info";
}

function NotificationItem({ title, description, time, severity = "info" }: NotificationItemProps) {
  const dotColors = {
    critical: "bg-critical",
    warning: "bg-warning",
    success: "bg-success",
    info: "bg-info",
  };

  return (
    <div className="px-3 py-3 hover:bg-muted/50 cursor-pointer transition-colors">
      <div className="flex gap-3">
        <div className={cn("w-2 h-2 mt-2 rounded-full shrink-0", dotColors[severity])} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs text-muted-foreground truncate">{description}</p>
          <p className="text-xs text-muted-foreground/70 mt-1">{time}</p>
        </div>
      </div>
    </div>
  );
}

// Page header with breadcrumbs
interface PageHeaderProps {
  breadcrumbs?: { label: string; href?: string }[];
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ breadcrumbs, title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between", className)}>
      <div>
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav className="flex items-center gap-1 text-sm text-muted-foreground mb-2">
            {breadcrumbs.map((crumb, index) => (
              <React.Fragment key={index}>
                {crumb.href ? (
                  <Link href={crumb.href} className="hover:text-foreground transition-colors">
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="text-foreground">{crumb.label}</span>
                )}
                {index < breadcrumbs.length - 1 && <span className="mx-1">/</span>}
              </React.Fragment>
            ))}
          </nav>
        )}
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && (
          <p className="text-muted-foreground mt-1">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
