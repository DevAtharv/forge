$src = [System.IO.File]::ReadAllText("index.html", [System.Text.Encoding]::UTF8)

$startMarker = "<!-- Dashboard -->"
$endMarker = "</section>`r`n`r`n    <script"

$si = $src.IndexOf($startMarker)
$ei = $src.IndexOf($endMarker)

if ($si -lt 0 -or $ei -lt 0) {
    Write-Error "Markers not found! si=$si ei=$ei"
    exit 1
}

$before = $src.Substring(0, $si)
$after  = $src.Substring($ei + "</section>".Length)

$newDash = @"
<!-- Dashboard -->
    <section class="dashboard-view view hidden" data-view="dashboard">
      <div id="dashboard-sidebar-overlay" class="drawer-overlay" aria-hidden="true"></div>
      <div class="dashboard-shell">
        <aside class="dashboard-sidebar" id="dashboard-sidebar" aria-label="Workspace navigation">
          <!-- Logo -->
          <div class="mf-sidebar-logo">
            <a class="site-logo route-link" data-route-link="home" href="#/home" aria-label="Forge home">
              <span class="site-logo__grid"><span></span></span>
              <span>ForgeWorkspace</span>
            </a>
          </div>

          <nav class="sidebar-links mf-sidebar-nav">
            <a class="sidebar-link mf-sidebar-link--active" href="#/dashboard">
              <span class="material-symbols-outlined">dashboard</span><span>Overview</span>
            </a>
            <a class="sidebar-link" href="#/dashboard">
              <span class="material-symbols-outlined">rocket_launch</span><span>Missions</span>
            </a>
            <a class="sidebar-link" href="#/dashboard">
              <span class="material-symbols-outlined">folder</span><span>Artifacts</span>
            </a>
            <a class="sidebar-link" href="#/dashboard">
              <span class="material-symbols-outlined">local_shipping</span><span>Delivery</span>
            </a>
            <a class="sidebar-link" href="#/dashboard">
              <span class="material-symbols-outlined">settings</span><span>Settings</span>
            </a>
          </nav>

          <div class="mf-sidebar-spacer"></div>

          <div class="sidebar-links mf-sidebar-bottom-nav">
            <a class="sidebar-link" href="#/dashboard">
              <span class="material-symbols-outlined">monitor_heart</span><span>System Status</span>
            </a>
            <a class="sidebar-link" href="#/dashboard">
              <span class="material-symbols-outlined">help_outline</span><span>Help</span>
            </a>
          </div>

          <div class="mf-sidebar-init">
            <div class="mf-sidebar-init-label">INITIALIZE MISSION</div>
            <button class="mf-new-thread-btn" type="button">New Thread</button>
          </div>
        </aside>

        <main class="dashboard-main">
          <button type="button" class="icon-btn" id="dashboard-nav-toggle" aria-label="Open sidebar" aria-expanded="false">
            <span class="material-symbols-outlined">menu</span>
          </button>

          <!-- Top header bar -->
          <header class="mf-header">
            <div class="mf-header__title-block">
              <h1 class="mf-header__title">Mainframe <span class="mf-accent">Dashboard</span></h1>
              <p class="mf-header__sub">Operational overview for forge instance 0x7E3</p>
            </div>
            <div class="mf-header__stats">
              <div class="mf-stat-chip">
                <span class="mf-stat-num" id="mission-count-metric">12</span>
                <div>
                  <div class="mf-stat-label">TOTAL MISSIONS</div>
                  <div class="mf-stat-status"><span class="mf-dot mf-dot--blue"></span> SYSTEM NOMINAL</div>
                </div>
              </div>
              <div class="mf-stat-chip mf-stat-chip--pink">
                <span class="mf-stat-num mf-stat-num--pink" id="active-mission-metric">03</span>
                <div>
                  <div class="mf-stat-label">ACTIVE RUNNING</div>
                  <div class="mf-stat-status"><span class="mf-dot mf-dot--pink"></span> EN QUEUE</div>
                </div>
              </div>
            </div>
          </header>

          <!-- Tabs -->
          <div class="mf-tabs">
            <button class="mf-tab mf-tab--active" type="button">Overview</button>
            <button class="mf-tab" type="button">Projects</button>
            <button class="mf-tab" type="button">Deployments</button>
          </div>

          <div class="mf-layout">
            <!-- Centre content column -->
            <div class="mf-content-col">

              <!-- Mission Control Panel -->
              <section class="mf-card mf-control-panel">
                <div class="mf-card__header">
                  <div class="mf-card__title-row">
                    <span class="material-symbols-outlined mf-sparkle">auto_awesome</span>
                    <span class="mf-card__title">MISSION CONTROL PANEL</span>
                  </div>
                  <div class="mf-engine-status">
                    <span class="mf-dot mf-dot--blue"></span> AI ENGINE ONLINE
                  </div>
                </div>
                <div class="mf-control-body">
                  <div class="mf-deploy-icon">
                    <span class="material-symbols-outlined">rocket_launch</span>
                  </div>
                  <h2 class="mf-deploy-title">Ready for Deployment</h2>
                  <p class="mf-deploy-sub">
                    Initialize your mission parameters in the console below.<br>
                    Our AI mainframe will orchestrate the artifacts and pipeline.
                  </p>
                  <div class="mf-tag-row">
                    <span class="mf-tag">BUILD UI FRAMEWORK</span>
                    <span class="mf-tag">DATA ANALYSIS V2</span>
                    <span class="mf-tag">CLOUD DEPLOY</span>
                    <button class="mf-run-btn" type="button" id="workspace-run">
                      <span class="material-symbols-outlined">play_arrow</span> Run Mission
                    </button>
                  </div>
                </div>
                <div class="mf-console-input">
                  <textarea id="workspace-input" placeholder="Define your next mission..."></textarea>
                </div>
              </section>

              <!-- Output & Artifacts -->
              <section class="mf-card mf-artifacts-panel">
                <div class="mf-card__header">
                  <div class="mf-card__title-row">
                    <span class="material-symbols-outlined mf-artifacts-icon">grid_view</span>
                    <span class="mf-card__title">Output &amp; Artifacts</span>
                  </div>
                  <button class="mf-view-archives" type="button">VIEW ARCHIVES</button>
                </div>
                <div class="mf-artifacts-body">
                  <div class="mf-artifact-thumb" id="artifact-list">
                    <div class="mf-artifact-thumb-inner">
                      <span class="mf-artifact-thumb-label">EMPTY PAYLOAD</span>
                    </div>
                  </div>
                  <div class="mf-artifacts-empty-text">
                    <p>No artifacts generated yet.</p>
                    <p class="muted">Submit a mission request to see results here.</p>
                  </div>
                </div>
              </section>

            </div><!-- /mf-content-col -->

            <!-- Right panel -->
            <aside class="mf-right-panel">

              <!-- Active Pipeline -->
              <section class="mf-card mf-pipeline-card">
                <div class="mf-panel-head-row">
                  <div class="mf-panel-kicker">ACTIVE PIPELINE</div>
                  <div class="mf-pipeline-progress">
                    <span class="mf-progress-text">0/4</span>
                    <span class="mf-progress-badge">COMPLETED</span>
                  </div>
                </div>
                <div class="mf-pipeline-stages" id="result-stages">
                  <div class="mf-stage">
                    <span class="mf-stage-icon mf-stage-icon--blue">
                      <span class="material-symbols-outlined">storage</span>
                    </span>
                    <div class="mf-stage-body">
                      <div class="mf-stage-title">Data Ingestion <span class="mf-stage-badge mf-badge--running">RUNNING</span></div>
                      <div class="mf-stage-desc">Parsing raw intelligence streams for mission context.</div>
                    </div>
                  </div>
                  <div class="mf-stage">
                    <span class="mf-stage-icon mf-stage-icon--dim">
                      <span class="material-symbols-outlined">account_tree</span>
                    </span>
                    <div class="mf-stage-body">
                      <div class="mf-stage-title">Context Mapping <span class="mf-stage-badge mf-badge--queued">QUEUED</span></div>
                      <div class="mf-stage-desc">Building semantic relationships across datasets.</div>
                    </div>
                  </div>
                  <div class="mf-stage">
                    <span class="mf-stage-icon mf-stage-icon--dim">
                      <span class="material-symbols-outlined">precision_manufacturing</span>
                    </span>
                    <div class="mf-stage-body">
                      <div class="mf-stage-title">Synthesis Engine <span class="mf-stage-badge mf-badge--queued">QUEUED</span></div>
                      <div class="mf-stage-desc">AI processing and artifact generation phase.</div>
                    </div>
                  </div>
                  <div class="mf-stage">
                    <span class="mf-stage-icon mf-stage-icon--dim">
                      <span class="material-symbols-outlined">verified</span>
                    </span>
                    <div class="mf-stage-body">
                      <div class="mf-stage-title">Validation &amp; Output <span class="mf-stage-badge mf-badge--queued">QUEUED</span></div>
                      <div class="mf-stage-desc">Final integrity check before delivery.</div>
                    </div>
                  </div>
                </div>
              </section>

              <!-- Compute Resources -->
              <section class="mf-card mf-compute-card">
                <div class="mf-compute-title">COMPUTE RESOURCES</div>
                <div class="mf-resource">
                  <div class="mf-resource-row">
                    <span class="mf-resource-label">GPU VRAM Usage</span>
                    <span class="mf-resource-value">64%</span>
                  </div>
                  <div class="mf-progress-bar">
                    <div class="mf-progress-fill mf-fill--blue" style="width:64%"></div>
                  </div>
                </div>
                <div class="mf-resource">
                  <div class="mf-resource-row">
                    <span class="mf-resource-label">Neural Credits</span>
                    <span class="mf-resource-value">1,240 / 5k</span>
                  </div>
                  <div class="mf-progress-bar">
                    <div class="mf-progress-fill mf-fill--pink" style="width:24.8%"></div>
                  </div>
                </div>
              </section>

              <!-- Recent Nodes -->
              <section class="mf-card mf-nodes-card">
                <div class="mf-compute-title">RECENT NODES</div>
                <div class="mf-node">
                  <span class="mf-node-dot mf-node-dot--blue"></span>
                  <div>
                    <div class="mf-node-name">Artifact-291-v2.json</div>
                    <div class="mf-node-meta">2 mins ago • Deployment</div>
                  </div>
                </div>
                <div class="mf-node">
                  <span class="mf-node-dot mf-node-dot--dim"></span>
                  <div>
                    <div class="mf-node-name">System-Handshake-OK</div>
                    <div class="mf-node-meta">14 mins ago • Connection</div>
                  </div>
                </div>
              </section>

            </aside>
          </div><!-- /mf-layout -->

          <div class="dashboard-footer-links">
            <a class="route-link" data-route-link="home" href="#/home">Home</a>
            <a class="route-link" data-route-link="auth" href="#/auth">Auth</a>
            <a class="route-link" data-route-link="dashboard" href="#/dashboard">Dashboard</a>
          </div>
        </main>
      </div>

      <button class="system-fab" type="button" aria-label="Support">
        <span class="material-symbols-outlined">support_agent</span>
      </button>
    </section>
"@

$result = $before + $newDash + $after
[System.IO.File]::WriteAllText("index.html", $result, [System.Text.Encoding]::UTF8)
Write-Host "Done. New length: $($result.Length)"
