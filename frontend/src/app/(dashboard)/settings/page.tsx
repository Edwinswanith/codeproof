"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  Settings,
  User,
  Bell,
  Shield,
  Palette,
  Key,
  Github,
  Webhook,
  Save,
  Check,
} from "lucide-react";
import { PageContainer } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const [saved, setSaved] = React.useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <PageContainer>
      <PageHeader
        title="Settings"
        description="Manage your account and preferences"
      />

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList variant="underline">
          <TabsTrigger value="profile" variant="underline" className="gap-2">
            <User className="h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="notifications" variant="underline" className="gap-2">
            <Bell className="h-4 w-4" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="integrations" variant="underline" className="gap-2">
            <Github className="h-4 w-4" />
            Integrations
          </TabsTrigger>
          <TabsTrigger value="security" variant="underline" className="gap-2">
            <Shield className="h-4 w-4" />
            Security
          </TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile">
          <div className="grid gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Profile Information</CardTitle>
                <CardDescription>
                  Update your personal information and preferences
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center gap-6">
                  <Avatar size="xl">
                    <AvatarImage src="https://avatars.githubusercontent.com/u/1234567" />
                    <AvatarFallback>JD</AvatarFallback>
                  </Avatar>
                  <div>
                    <Button variant="outline" size="sm">Change Avatar</Button>
                    <p className="text-xs text-muted-foreground mt-2">
                      JPG, PNG or GIF. Max 2MB.
                    </p>
                  </div>
                </div>

                <Separator />

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Name</label>
                    <Input defaultValue="John Doe" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Email</label>
                    <Input defaultValue="john@example.com" type="email" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">GitHub Username</label>
                    <Input defaultValue="johndoe" disabled />
                    <p className="text-xs text-muted-foreground">
                      Synced from GitHub
                    </p>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Company</label>
                    <Input defaultValue="Acme Inc" />
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button onClick={handleSave} variant="glow">
                    {saved ? (
                      <>
                        <Check className="h-4 w-4 mr-2" />
                        Saved
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        Save Changes
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Palette className="h-5 w-5" />
                  Appearance
                </CardTitle>
                <CardDescription>
                  Customize the look and feel of the interface
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Theme</p>
                      <p className="text-sm text-muted-foreground">
                        Choose your preferred theme
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <ThemeOption theme="dark" active />
                      <ThemeOption theme="light" />
                      <ThemeOption theme="system" />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>
                Choose what notifications you want to receive
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <NotificationSetting
                title="PR Review Complete"
                description="Get notified when a PR analysis is finished"
                defaultEnabled
              />
              <Separator />
              <NotificationSetting
                title="Critical Findings"
                description="Immediate alerts for critical security issues"
                defaultEnabled
              />
              <Separator />
              <NotificationSetting
                title="Usage Alerts"
                description="Warnings when approaching usage limits"
                defaultEnabled
              />
              <Separator />
              <NotificationSetting
                title="Weekly Digest"
                description="Weekly summary of activity and findings"
              />
              <Separator />
              <NotificationSetting
                title="Marketing Emails"
                description="Product updates and announcements"
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Integrations Tab */}
        <TabsContent value="integrations">
          <div className="grid gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Github className="h-5 w-5" />
                  GitHub Integration
                </CardTitle>
                <CardDescription>
                  Manage your GitHub connection and permissions
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg bg-success/5 border border-success/20">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-success" />
                    <div>
                      <p className="font-medium">Connected</p>
                      <p className="text-sm text-muted-foreground">
                        @johndoe · 12 repositories
                      </p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm">Manage</Button>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Permissions</p>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="terminal">Read repository contents</Badge>
                    <Badge variant="terminal">Write pull request reviews</Badge>
                    <Badge variant="terminal">Read organization data</Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Webhook className="h-5 w-5" />
                  Webhooks
                </CardTitle>
                <CardDescription>
                  Configure webhook notifications
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Webhook URL</label>
                    <Input placeholder="https://your-server.com/webhook" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Secret</label>
                    <Input type="password" placeholder="Webhook secret" />
                  </div>
                  <Button variant="outline">Test Webhook</Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security">
          <div className="grid gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Key className="h-5 w-5" />
                  API Keys
                </CardTitle>
                <CardDescription>
                  Manage API keys for programmatic access
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 rounded-lg border border-border">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-mono text-sm">cp_live_xxxx...xxxx</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Created Dec 15, 2024 · Last used 2 hours ago
                      </p>
                    </div>
                    <Button variant="outline" size="sm" className="text-destructive">
                      Revoke
                    </Button>
                  </div>
                </div>
                <Button variant="outline">
                  <Key className="h-4 w-4 mr-2" />
                  Create New API Key
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Sessions</CardTitle>
                <CardDescription>
                  Manage your active sessions
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 rounded-lg bg-success/5 border border-success/20">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">Current Session</p>
                        <Badge variant="success" size="sm">Active</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        Chrome on macOS · San Francisco, CA
                      </p>
                    </div>
                  </div>
                </div>
                <Button variant="outline" className="text-destructive">
                  Sign Out All Other Sessions
                </Button>
              </CardContent>
            </Card>

            <Card className="border-destructive/50">
              <CardHeader>
                <CardTitle className="text-destructive">Danger Zone</CardTitle>
                <CardDescription>
                  Irreversible actions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Delete Account</p>
                    <p className="text-sm text-muted-foreground">
                      Permanently delete your account and all data
                    </p>
                  </div>
                  <Button variant="destructive">Delete Account</Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}

// Theme Option
function ThemeOption({ theme, active }: { theme: string; active?: boolean }) {
  return (
    <button
      className={cn(
        "w-16 h-10 rounded-md border-2 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary/10 text-primary"
          : "border-border hover:border-primary/50"
      )}
    >
      {theme.charAt(0).toUpperCase() + theme.slice(1)}
    </button>
  );
}

// Notification Setting
function NotificationSetting({
  title,
  description,
  defaultEnabled,
}: {
  title: string;
  description: string;
  defaultEnabled?: boolean;
}) {
  const [enabled, setEnabled] = React.useState(defaultEnabled ?? false);

  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <button
        onClick={() => setEnabled(!enabled)}
        className={cn(
          "relative w-11 h-6 rounded-full transition-colors",
          enabled ? "bg-primary" : "bg-muted"
        )}
      >
        <span
          className={cn(
            "absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform",
            enabled && "translate-x-5"
          )}
        />
      </button>
    </div>
  );
}
