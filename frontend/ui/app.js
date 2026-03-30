const SESSION_KEY = "forge.supabase.session";
const API_BASE = (window.FORGE_API_BASE_URL || "").replace(/\/$/, "");

const state = {
  authMode: "signin",
  authEnabled: false,
  session: null,
  user: null,
};

const els = {
  healthText: document.getElementById("health-text"),
  healthDot: document.getElementById("health-dot"),
  authText: document.getElementById("auth-text"),
  authDot: document.getElementById("auth-dot"),
  authForm: document.getElementById("auth-form"),
  authSubmit: document.getElementById("auth-submit"),
  authEmail: document.getElementById("auth-email"),
  authPassword: document.getElementById("auth-password"),
  authFeedback: document.getElementById("auth-feedback"),
  authWarning: document.getElementById("auth-warning"),
  modeSignin: document.getElementById("mode-signin"),
  modeSignup: document.getElementById("mode-signup"),
  workspaceUser: document.getElementById("workspace-user"),
  workspaceUserMeta: document.getElementById("workspace-user-meta"),
  missionStatusChip: document.getElementById("mission-status-chip"),
  workspaceInput: document.getElementById("workspace-input"),
  workspaceRun: document.getElementById("workspace-run"),
  workspaceFill: document.getElementById("workspace-fill"),
  previewRun: document.getElementById("preview-run"),
  workspaceFeedback: document.getElementById("workspace-feedback"),
  signoutButton: document.getElementById("signout-button"),
  resultMeta: document.getElementById("result-meta"),
  resultResponse: document.getElementById("result-response"),
  documentWrap: document.getElementById("document-wrap"),
  documentOutput: document.getElementById("document-output"),
  resultIntent: document.getElementById("result-intent"),
  resultContext: document.getElementById("result-context"),
  resultStages: document.getElementById("result-stages"),
  profileSummary: document.getElementById("profile-summary"),
  profileStackList: document.getElementById("profile-stack-list"),
  profileProjectsList: document.getElementById("profile-projects-list"),
  profileContextList: document.getElementById("profile-context-list"),
  profileSkill: document.getElementById("profile-skill"),
  timelineList: document.getElementById("timeline-list"),
  timelineMeta: document.getElementById("timeline-meta"),
  artifactList: document.getElementById("artifact-list"),
  artifactMeta: document.getElementById("artifact-meta"),
  terminalMeta: document.getElementById("terminal-meta"),
  terminalOutput: document.getElementById("terminal-output"),
  telegramLinkStatus: document.getElementById("telegram-link-status"),
  telegramLinkCode: document.getElementById("telegram-link-code"),
  telegramLinkExpiry: document.getElementById("telegram-link-expiry"),
  telegramLinkAction: document.getElementById("telegram-link-action"),
  telegramLinkHelp: document.getElementById("telegram-link-help"),
};

const views = [...document.querySelectorAll("[data-view]")];
const routeLinks = [...document.querySelectorAll("[data-route-link]")];
const homeModeCopy = document.getElementById("home-mode-copy");

function setDot(element, color) {
  element.style.background = color;
}

function isAuthenticated() {
  return Boolean(state.user && state.session && state.session.access_token);
}

function normalizeRoute(hash = window.location.hash) {
  const route = hash.replace(/^#\/?/, "").split("?")[0].split("/")[0] || "home";
  return ["home", "auth", "dashboard"].includes(route) ? route : "home";
}

function buildIntegrationConnectUrl(provider) {
  return `${API_BASE}/api/integrations/${provider}/start`;
}

function navigate(route, replace = false) {
  const nextHash = `#/${route}`;
  if (replace) {
    window.history.replaceState(null, "", nextHash);
    renderRoute();
    return;
  }
  if (window.location.hash === nextHash) {
    renderRoute();
    return;
  }
  window.location.hash = nextHash;
}

function renderRoute() {
  let route = normalizeRoute();

  if (route === "dashboard" && !isAuthenticated()) {
    route = state.authEnabled ? "auth" : "home";
    window.history.replaceState(null, "", `#/${route}`);
  }

  views.forEach((view) => {
    view.classList.toggle("hidden", view.dataset.view !== route);
  });

  routeLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.routeLink === route);
  });
}

function consumeIntegrationStatus() {
  const current = new URL(window.location.href);
  const provider = current.searchParams.get("integration");
  const status = current.searchParams.get("status");
  const message = current.searchParams.get("message");
  const account = current.searchParams.get("account");

  if (!provider || !status) {
    return;
  }

  if (status === "connected") {
    els.workspaceFeedback.textContent = message || `${provider} connected${account ? ` as ${account}` : ""}.`;
  } else {
    els.workspaceFeedback.textContent = message || `${provider} connection failed.`;
  }

  current.search = "";
  window.history.replaceState(null, "", current.toString());
}

function fetchJson(url, options) {
  const target = url.startsWith("http://") || url.startsWith("https://") ? url : `${API_BASE}${url}`;
  return fetch(target, options).then(async (response) => {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || "Request failed.");
    }
    return payload;
  });
}

function authHeaders() {
  if (!(state.session && state.session.access_token)) {
    throw new Error("Sign in first to use the protected workspace.");
  }
  return { Authorization: `Bearer ${state.session.access_token}` };
}

function fetchAuthedJson(url, options = {}) {
  return fetchJson(url, {
    ...options,
    headers: { ...(options.headers || {}), ...authHeaders() },
  });
}

function setAuthMode(mode) {
  state.authMode = mode;
  els.modeSignin.classList.toggle("active", mode === "signin");
  els.modeSignup.classList.toggle("active", mode === "signup");
  els.authSubmit.textContent = mode === "signin" ? "Sign In" : "Create Account";
  els.authFeedback.textContent =
    mode === "signin"
      ? "Use your Supabase credentials to unlock the protected workspace."
      : "Create a Forge account. Email confirmation depends on your Supabase settings.";
}

function saveSession(session, user) {
  state.session = session;
  state.user = user;
  localStorage.setItem(SESSION_KEY, JSON.stringify({ session, user }));
}

function clearSession() {
  state.session = null;
  state.user = null;
  localStorage.removeItem(SESSION_KEY);
}

function loadStoredSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_error) {
    return null;
  }
}

function renderAuthState() {
  const active = isAuthenticated();
  els.missionStatusChip.textContent = active ? "Protected workspace active" : "Public preview mode";
  els.workspaceRun.disabled = !active;
  els.signoutButton.disabled = !active;
  els.telegramLinkAction.disabled = !active;
  if (homeModeCopy) {
    homeModeCopy.textContent = active ? "Authenticated workspace" : "Protected workspace";
  }

  if (!active) {
    els.workspaceUser.textContent = "Not signed in";
    els.workspaceUserMeta.textContent = state.authEnabled
      ? "Sign in to open the protected mission console."
      : "Supabase auth is not configured yet.";
    renderTelegramLink(null);
    renderRoute();
    return;
  }

  els.workspaceUser.textContent = state.user.email || "Authenticated Forge user";
  els.workspaceUserMeta.textContent =
    "Forge will fetch your profile and conversation memory through protected backend APIs.";
  renderRoute();
}

function renderTelegramLink(link) {
  if (!link) {
    els.telegramLinkStatus.textContent = "Sign in to generate a Telegram link code.";
    els.telegramLinkCode.textContent = "No active code";
    els.telegramLinkExpiry.textContent = "Generate a code, then send /link CODE to the Forge Telegram bot.";
    els.telegramLinkHelp.textContent = "Telegram messages will share this workspace after linking.";
    els.telegramLinkAction.textContent = "Generate Link Code";
    return;
  }

  const botHandle = link.bot_username ? `@${link.bot_username}` : "the Forge Telegram bot";
  if (link.linked) {
    const username = link.telegram_username ? `@${link.telegram_username}` : `Telegram user ${link.telegram_user_id}`;
    els.telegramLinkStatus.textContent = `Connected to ${username}. Telegram and website now share this Forge workspace.`;
    els.telegramLinkCode.textContent = "Connected";
    els.telegramLinkExpiry.textContent = `Future Telegram messages to ${botHandle} will use this website memory.`;
    els.telegramLinkHelp.textContent = "Generate a fresh code only if you want to relink a different Telegram account.";
    els.telegramLinkAction.textContent = "Refresh Link Code";
    return;
  }

  if (link.pending_code) {
    els.telegramLinkStatus.textContent = `Pending link. Send /link ${link.pending_code} to ${botHandle}.`;
    els.telegramLinkCode.textContent = link.pending_code;
    els.telegramLinkExpiry.textContent = link.pending_expires_at
      ? `Expires ${formatDate(link.pending_expires_at)}`
      : `Send /link ${link.pending_code} to ${botHandle}.`;
    els.telegramLinkHelp.textContent = `Open Telegram and send /link ${link.pending_code} to ${botHandle}.`;
    els.telegramLinkAction.textContent = "Refresh Link Code";
    return;
  }

  els.telegramLinkStatus.textContent = `No Telegram account linked yet. Generate a code, then send /link CODE to ${botHandle}.`;
  els.telegramLinkCode.textContent = "No active code";
  els.telegramLinkExpiry.textContent = `After linking, Telegram messages to ${botHandle} will share this workspace.`;
  els.telegramLinkHelp.textContent = "Telegram messages will share this workspace after linking.";
  els.telegramLinkAction.textContent = "Generate Link Code";
}

function formatDate(value) {
  if (!value) {
    return "just now";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "just now";
  }
  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderTags(container, values, emptyText, neutral = false) {
  container.innerHTML = "";
  if (!values || !values.length) {
    const chip = document.createElement("span");
    chip.className = "chip neutral";
    chip.textContent = emptyText;
    container.appendChild(chip);
    return;
  }
  for (const value of values) {
    const chip = document.createElement("span");
    chip.className = neutral ? "chip neutral" : "chip";
    chip.textContent = String(value);
    container.appendChild(chip);
  }
}

function renderProfile(profile) {
  if (!profile) {
    els.profileSummary.textContent = "Sign in to load the workspace profile.";
    renderTags(els.profileStackList, [], "No stack captured yet");
    renderTags(els.profileProjectsList, [], "No active projects captured yet");
    renderTags(els.profileContextList, [], "No active context captured yet");
    els.profileSkill.textContent = "Skill level: intermediate";
    return;
  }

  const contextEntries = Object.entries(profile.active_context || {}).map(([key, value]) => `${key}: ${value}`);
  els.profileSummary.textContent =
    profile.summary ||
    "Forge will grow this summary over time as more authenticated missions are completed.";
  renderTags(els.profileStackList, profile.stack || [], "No stack captured yet");
  renderTags(els.profileProjectsList, profile.current_projects || [], "No active projects captured yet");
  renderTags(els.profileContextList, contextEntries, "No active context captured yet");
  els.profileSkill.textContent = `Skill level: ${profile.skill_level || "intermediate"} • Messages: ${profile.message_count || 0}`;
}

function renderHistory(history) {
  els.timelineList.innerHTML = "";
  if (!history || !history.length) {
    els.timelineList.innerHTML = '<div class="empty">Conversation history will appear here after your first mission.</div>';
    els.timelineMeta.textContent = "No stored conversation yet";
    return;
  }

  els.timelineMeta.textContent = `${history.length} stored message${history.length === 1 ? "" : "s"}`;
  history
    .slice()
    .reverse()
    .forEach((item) => {
      const card = document.createElement("div");
      card.className = "timeline-item";

      const head = document.createElement("div");
      head.className = "split";

      const role = document.createElement("span");
      role.className = `timeline-role ${item.role}`;
      role.textContent = item.role;

      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent = formatDate(item.created_at);

      const body = document.createElement("p");
      body.className = "timeline-body";
      body.textContent = item.content;

      head.appendChild(role);
      head.appendChild(meta);
      card.appendChild(head);
      card.appendChild(body);

      if (item.agents_used && item.agents_used.length) {
        const badges = document.createElement("div");
        badges.className = "badges";
        item.agents_used.forEach((agent) => {
          const chip = document.createElement("span");
          chip.className = "chip neutral";
          chip.textContent = agent;
          badges.appendChild(chip);
        });
        card.appendChild(badges);
      }

      els.timelineList.appendChild(card);
    });
}

function renderPlan(plan, sourceLabel) {
  els.resultStages.innerHTML = "";
  els.resultIntent.textContent = plan.intent;
  els.resultContext.textContent = `${plan.response_format} • ${plan.context_policy.replaceAll("_", " ")}`;
  els.resultMeta.textContent = sourceLabel;

  if (!plan.stages || !plan.stages.length) {
    els.resultStages.innerHTML = '<div class="empty">Forge did not return any stages for this request.</div>';
    return;
  }

  plan.stages.forEach((stage) => {
    const card = document.createElement("div");
    card.className = "stage";

    const head = document.createElement("div");
    head.className = "stage-head";

    const name = document.createElement("strong");
    name.textContent = stage.name;

    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = `${stage.agents.length} agent${stage.agents.length === 1 ? "" : "s"}`;

    const badges = document.createElement("div");
    badges.className = "badges";
    stage.agents.forEach((agent) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = `${agent}: ${stage.tasks[agent] || "active"}`;
      badges.appendChild(chip);
    });

    head.appendChild(name);
    head.appendChild(meta);
    card.appendChild(head);
    card.appendChild(badges);
    els.resultStages.appendChild(card);
  });
}

function renderDelivery(delivery) {
  if (!delivery) {
    els.resultResponse.textContent = "Sign in and run a mission to see the aggregated Forge answer here.";
    els.documentWrap.classList.add("hidden");
    els.documentOutput.textContent = "";
    return;
  }

  els.resultResponse.textContent = delivery.text || "Forge completed the mission without a visible response.";
  if (delivery.document_text) {
    els.documentWrap.classList.remove("hidden");
    els.documentOutput.textContent = delivery.document_text;
  } else {
    els.documentWrap.classList.add("hidden");
    els.documentOutput.textContent = "";
  }
}

function renderApprovalPrompt(mission) {
  const approval = mission.approval_request || {};
  const provider =
    approval.action === "connect_vercel"
      ? "vercel"
      : approval.action === "connect_github"
        ? "github"
        : null;

  els.resultResponse.innerHTML = "";

  const body = document.createElement("div");
  body.className = "approval-callout";

  const message = document.createElement("p");
  message.className = "response-text";
  message.textContent =
    mission.response_text ||
    approval.message ||
    "Forge needs one more connection before this mission can continue.";
  body.appendChild(message);

  if (provider) {
    const action = document.createElement("a");
    action.className = "primary-button approval-button";
    action.href = buildIntegrationConnectUrl(provider);
    action.textContent = provider === "vercel" ? "Connect Vercel" : "Connect GitHub";
    body.appendChild(action);

    const hint = document.createElement("p");
    hint.className = "muted";
    hint.style.margin = "12px 0 0";
    hint.textContent =
      provider === "vercel"
        ? "After Vercel connects, run deploy again and Forge will send the project live."
        : "After GitHub connects, run build again and Forge will save the generated files to your repo.";
    body.appendChild(hint);
  }

  els.resultResponse.appendChild(body);
}

function renderArtifacts(stages, delivery) {
  els.artifactList.innerHTML = "";
  const artifacts = [];

  (stages || []).forEach((stage) => {
    Object.entries(stage.outputs || {}).forEach(([agent, output]) => {
      (output.artifacts || []).forEach((artifact) => {
        artifacts.push({ stage: stage.name, agent, ...artifact });
      });
    });
  });

  if (!artifacts.length && !(delivery && delivery.document_text)) {
    els.artifactList.innerHTML = '<div class="empty">Artifacts from planner, code, or reviewer outputs will appear here.</div>';
    els.artifactMeta.textContent = "No artifacts yet";
    return;
  }

  els.artifactMeta.textContent = artifacts.length
    ? `${artifacts.length} artifact${artifacts.length === 1 ? "" : "s"}`
    : "Document attached";

  artifacts.forEach((artifact) => {
    const card = document.createElement("div");
    card.className = "artifact";

    const head = document.createElement("div");
    head.className = "artifact-head";

    const title = document.createElement("strong");
    title.textContent = artifact.name;

    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = `${artifact.agent} • ${artifact.stage}${artifact.language ? ` • ${artifact.language}` : ""}`;

    const pre = document.createElement("pre");
    pre.textContent = artifact.content;

    head.appendChild(title);
    head.appendChild(meta);
    card.appendChild(head);
    card.appendChild(pre);
    els.artifactList.appendChild(card);
  });
}

function renderMissionArtifacts(mission) {
  els.artifactList.innerHTML = "";
  const changedFiles = mission.changed_files || [];

  if (!changedFiles.length) {
    renderArtifacts([], null);
    return;
  }

  els.artifactMeta.textContent = `${changedFiles.length} file${changedFiles.length === 1 ? "" : "s"}`;

  changedFiles.forEach((fileName) => {
    const card = document.createElement("div");
    card.className = "artifact";

    const head = document.createElement("div");
    head.className = "artifact-head";

    const title = document.createElement("strong");
    title.textContent = fileName;

    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = mission.repo_url ? "Synced to GitHub" : "Generated by Forge";

    head.appendChild(title);
    head.appendChild(meta);
    card.appendChild(head);

    if (mission.repo_url || mission.deployment_url) {
      const body = document.createElement("p");
      body.className = "timeline-body";
      body.textContent = mission.deployment_url
        ? `Live: ${mission.deployment_url}`
        : `Repo: ${mission.repo_url}`;
      card.appendChild(body);
    }

    els.artifactList.appendChild(card);
  });
}

function renderMissionTerminal(mission) {
  const lines = [];

  if (mission.repo_url) {
    lines.push(`GitHub repo: ${mission.repo_url}`);
  }
  if (mission.deployment_url) {
    lines.push(`Deployment URL: ${mission.deployment_url}`);
  }
  if (mission.changed_files && mission.changed_files.length) {
    lines.push("Changed files:");
    mission.changed_files.forEach((fileName) => lines.push(`- ${fileName}`));
  }

  if (!lines.length) {
    renderTerminal([], null);
    return;
  }

  els.terminalMeta.textContent = `${lines.length} line${lines.length === 1 ? "" : "s"}`;
  els.terminalOutput.textContent = lines.join("\n");
}

function renderMissionResult(mission) {
  if (mission.status === "awaiting_approval") {
    renderApprovalPrompt(mission);
    els.documentWrap.classList.add("hidden");
    els.documentOutput.textContent = "";
  } else {
    renderDelivery({
      text: mission.response_text || mission.result_summary || "Mission completed.",
    });
  }
  renderMissionArtifacts(mission);
  renderMissionTerminal(mission);
  els.resultMeta.textContent = mission.changed_files && mission.changed_files.length
    ? `${mission.changed_files.length} file${mission.changed_files.length === 1 ? "" : "s"} generated`
    : mission.status;
  els.resultIntent.textContent = mission.result_summary || mission.kind;
  els.resultContext.textContent = mission.deployment_url
    ? `${mission.kind} • ${mission.status} • deployed`
    : mission.repo_url
      ? `${mission.kind} • ${mission.status} • synced to GitHub`
      : `${mission.kind} • ${mission.status}`;
}

function extractTerminalCommands(stages, delivery) {
  const commands = [];
  const commandPattern =
    /^(?:npm|pnpm|yarn|npx|pip|python|uvicorn|vercel|docker|git|cd|cp|mv|mkdir|touch)\b/i;
  const pushLine = (line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }
    if (commandPattern.test(trimmed) && !commands.includes(trimmed)) {
      commands.push(trimmed);
    }
  };

  const allArtifacts = [];
  (stages || []).forEach((stage) => {
    Object.values(stage.outputs || {}).forEach((output) => {
      (output.artifacts || []).forEach((artifact) => allArtifacts.push(artifact));
    });
  });

  allArtifacts.forEach((artifact) => {
    const fileName = (artifact.name || "").toLowerCase();
    if (fileName.includes("terminal") || fileName.endsWith(".sh") || fileName.endsWith(".ps1")) {
      String(artifact.content || "")
        .split(/\r?\n/)
        .forEach(pushLine);
    }
  });

  const textBlob = `${delivery?.text || ""}\n${delivery?.document_text || ""}`;
  const fenceRegex = /```(?:bash|sh|zsh|powershell|pwsh)?\n([\s\S]*?)```/gi;
  let match;
  while ((match = fenceRegex.exec(textBlob)) !== null) {
    match[1].split(/\r?\n/).forEach(pushLine);
  }

  return commands;
}

function renderTerminal(stages, delivery) {
  const commands = extractTerminalCommands(stages, delivery);
  if (!commands.length) {
    els.terminalMeta.textContent = "No commands yet";
    els.terminalOutput.textContent = "Run a mission that asks Forge to build and deploy. Command steps will appear here.";
    return;
  }
  els.terminalMeta.textContent = `${commands.length} command${commands.length === 1 ? "" : "s"}`;
  els.terminalOutput.textContent = commands.join("\n");
}

async function checkHealth() {
  try {
    const payload = await fetchJson("/health");
    els.healthText.textContent = payload.status === "ok" ? "Backend live" : "Backend responded";
    setDot(els.healthDot, "var(--teal)");
  } catch (_error) {
    els.healthText.textContent = "Backend offline";
    setDot(els.healthDot, "var(--danger)");
  }
}

async function checkConfig() {
  try {
    const payload = await fetchJson("/api/client-config");
    state.authEnabled = Boolean(payload.auth_enabled);
    els.authText.textContent = state.authEnabled ? "Supabase auth ready" : "Supabase auth not configured";
    setDot(els.authDot, state.authEnabled ? "var(--teal)" : "var(--gold)");
    els.authWarning.classList.toggle("hidden", state.authEnabled);
    els.authWarning.classList.toggle("warn", !state.authEnabled);
    els.authWarning.textContent = state.authEnabled
      ? ""
      : "Add SUPABASE_URL and SUPABASE_ANON_KEY to enable sign-in and the protected workspace.";
  } catch (_error) {
    state.authEnabled = false;
    els.authText.textContent = "Could not load auth config";
    setDot(els.authDot, "var(--danger)");
  }
  renderAuthState();
}

async function loadDashboard() {
  if (!(state.session && state.session.access_token)) {
    renderProfile(null);
    renderHistory([]);
    return;
  }

  try {
    const payload = await fetchAuthedJson("/api/app/dashboard");
    state.user = payload.user;
    renderAuthState();
    renderProfile(payload.profile);
    renderHistory(payload.history);
    renderTelegramLink(payload.telegram_link);
    const projects = payload.projects || [];
    const missions = payload.missions || [];
    els.resultMeta.textContent = `${projects.length} project${projects.length === 1 ? "" : "s"} • ${(payload.integrations || []).length} integration${(payload.integrations || []).length === 1 ? "" : "s"}`;

    const latestMission = missions
      .slice()
      .sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0))[0];

    if (latestMission && (latestMission.response_text || latestMission.result_summary)) {
      renderMissionResult(latestMission);
    }
  } catch (error) {
    els.workspaceFeedback.textContent = error.message;
  }
}

async function pollMission(missionId) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const payload = await fetchAuthedJson(`/api/app/missions/${missionId}`);
    const mission = payload.mission;
    if (mission.status === "completed" || mission.status === "failed" || mission.status === "awaiting_approval") {
      return mission;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
  }
  throw new Error("Mission is still running. Check back in a moment.");
}

async function restoreSession() {
  const stored = loadStoredSession();
  if (!stored || !stored.session || !stored.session.access_token) {
    renderAuthState();
    renderProfile(null);
    renderHistory([]);
    renderRoute();
    return;
  }

  try {
    const payload = await fetchJson("/api/auth/session", {
      headers: { Authorization: `Bearer ${stored.session.access_token}` },
    });
    saveSession(stored.session, payload.user);
  } catch (_error) {
    clearSession();
  }

  renderAuthState();
  await loadDashboard();
  if (normalizeRoute() === "auth") {
    navigate("dashboard", true);
  } else {
    renderRoute();
  }
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  if (!state.authEnabled) {
    els.authFeedback.textContent = "Supabase auth is not configured yet.";
    return;
  }

  els.authSubmit.disabled = true;
  els.authFeedback.textContent =
    state.authMode === "signin" ? "Signing you in..." : "Creating your account...";

  try {
    const payload = await fetchJson(
      state.authMode === "signin" ? "/api/auth/signin" : "/api/auth/signup",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: els.authEmail.value.trim(),
          password: els.authPassword.value,
        }),
      },
    );

    if (payload.session && payload.session.access_token) {
      saveSession(payload.session, payload.user);
      els.authFeedback.textContent = payload.message || "Authenticated successfully.";
      renderAuthState();
      await loadDashboard();
      navigate("dashboard");
    } else {
      els.authFeedback.textContent =
        payload.message || "Account created. Check your inbox for confirmation.";
    }
  } catch (error) {
    els.authFeedback.textContent = error.message;
  } finally {
    els.authSubmit.disabled = false;
  }
}

async function runPreview() {
  const prompt = els.workspaceInput.value.trim();
  if (!prompt) {
    els.workspaceFeedback.textContent = "Add a mission prompt first.";
    return;
  }

  els.previewRun.disabled = true;
  els.workspaceFeedback.textContent = "Previewing the pipeline...";

  try {
    const payload = await fetchJson("/demo/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    renderPlan(payload.plan, "Public router preview");
    els.workspaceFeedback.textContent = `Previewed intent: ${payload.plan.intent}`;
  } catch (error) {
    els.workspaceFeedback.textContent = error.message;
  } finally {
    els.previewRun.disabled = false;
  }
}

async function runMission() {
  const prompt = els.workspaceInput.value.trim();
  if (!prompt) {
    els.workspaceFeedback.textContent = "Add a mission prompt first.";
    return;
  }
  if (!(state.session && state.session.access_token)) {
    els.workspaceFeedback.textContent = "Sign in first to run a protected mission.";
    return;
  }

  els.workspaceRun.disabled = true;
  els.workspaceFeedback.textContent = "Running the protected Forge mission...";

  try {
    const payload = await fetchAuthedJson("/api/app/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    state.user = payload.user;
    renderAuthState();
    renderProfile(payload.profile);
    renderHistory(payload.history);
    els.workspaceFeedback.textContent = payload.message || "Mission queued.";
    const mission = await pollMission(payload.mission.id);
    renderMissionResult(mission);
    els.resultStages.innerHTML = "";
    els.workspaceFeedback.textContent = `Mission ${mission.status}: ${mission.result_summary || mission.prompt}`;
    await loadDashboard();
  } catch (error) {
    els.workspaceFeedback.textContent = error.message;
  } finally {
    els.workspaceRun.disabled = false;
  }
}

async function linkTelegram() {
  if (!(state.session && state.session.access_token)) {
    els.telegramLinkHelp.textContent = "Sign in first to generate a Telegram link code.";
    return;
  }

  els.telegramLinkAction.disabled = true;
  els.telegramLinkHelp.textContent = "Generating your Telegram link code...";

  try {
    const payload = await fetchAuthedJson("/api/app/link/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: true }),
    });
    renderTelegramLink({
      linked: payload.linked,
      telegram_user_id: payload.telegram_user_id,
      telegram_username: payload.telegram_username,
      bot_username: payload.bot_username,
      pending_code: payload.code,
      pending_expires_at: payload.expires_at,
    });
    els.telegramLinkHelp.textContent = payload.message;
  } catch (error) {
    els.telegramLinkHelp.textContent = error.message;
  } finally {
    els.telegramLinkAction.disabled = false;
  }
}

async function signOut() {
  if (state.session && state.session.access_token) {
    try {
      await fetchJson("/api/auth/signout", {
        method: "POST",
        headers: { Authorization: `Bearer ${state.session.access_token}` },
      });
    } catch (_error) {
      // Ignore remote sign-out failures and still clear local state.
    }
  }

  clearSession();
  renderAuthState();
  renderProfile(null);
  renderHistory([]);
  renderDelivery(null);
  renderArtifacts([], null);
  renderTerminal([], null);
  renderTelegramLink(null);
  els.workspaceFeedback.textContent = "Signed out.";
  navigate("home");
}

els.modeSignin.addEventListener("click", () => setAuthMode("signin"));
els.modeSignup.addEventListener("click", () => setAuthMode("signup"));
els.authForm.addEventListener("submit", handleAuthSubmit);
els.previewRun.addEventListener("click", runPreview);
els.workspaceRun.addEventListener("click", runMission);
els.telegramLinkAction.addEventListener("click", linkTelegram);
els.workspaceFill.addEventListener("click", () => {
  els.workspaceInput.value =
    "Should I use Redis or Supabase for storing sessions in a production FastAPI app, and why?";
  els.workspaceFeedback.textContent = "Loaded a research-style mission.";
});
els.signoutButton.addEventListener("click", signOut);
window.addEventListener("hashchange", renderRoute);

setAuthMode("signin");
renderAuthState();
renderTelegramLink(null);
renderTerminal([], null);
renderRoute();
consumeIntegrationStatus();
checkHealth();
checkConfig().then(restoreSession);
runPreview();
