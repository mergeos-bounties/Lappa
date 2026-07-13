/* Lappa IDE client */
const API = "";
let demos = [];
let activePkg = null;
let openFile = null;
let editor = null;
let hotOn = true;
let simRunning = false;
let trail = [];
let keys = {};
let selectedMeshId = null;
let ros2Versions = [];
let viewMode = "2d"; // 2d | 3d
let scene3d = null;
let threeCtx = null; // { renderer, scene, camera, robot, nodes, drag }
let urdfSticks = null; // parsed URDF stick figure for the active package
let showSticks = true;

function log(msg) {
  const el = document.getElementById("console");
  el.textContent += msg + "\n";
  el.scrollTop = el.scrollHeight;
}

async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) return r.json();
  return r.text();
}

function setPill(text, cls) {
  const p = document.getElementById("status-pill");
  p.textContent = text;
  p.className = "pill " + (cls || "idle");
}

function renderTree(files) {
  const root = document.getElementById("file-tree");
  root.innerHTML = "";
  (files || []).forEach((f) => {
    const d = document.createElement("div");
    d.className = "item" + (openFile === f ? " on" : "");
    d.textContent = f;
    d.title = f;
    d.onclick = () => openPath(f);
    root.appendChild(d);
  });
}

function renderDemos() {
  const root = document.getElementById("demo-list");
  root.innerHTML = "";
  demos.forEach((d) => {
    const card = document.createElement("div");
    card.className = "demo-card";
    card.innerHTML = `<h4>${d.name}</h4><p>${d.description || "ROS2 package"}</p>`;
    card.onclick = () => loadDemo(d.name);
    root.appendChild(card);
  });
}

async function loadDemo(name) {
  log("open demo " + name);
  activePkg = await api("/api/workspace/open", {
    method: "POST",
    body: JSON.stringify({ demo: name }),
  });
  document.getElementById("pkg-label").textContent = activePkg.name;
  renderTree(activePkg.files);
  const prefer = activePkg.files.find((f) => f.endsWith("teleop.py"))
    || activePkg.files.find((f) => f === "package.xml")
    || activePkg.files[0];
  if (prefer) await openPath(prefer);
  await api("/api/sim/start", {
    method: "POST",
    body: JSON.stringify({ demo: name }),
  });
  simRunning = true;
  setPill("running", "run");
  trail = [];
  log("sim started: " + name + " (native)");
  loadUrdfSticks(name).catch((e) => log("urdf sticks: " + e.message));
  if (viewMode === "3d") {
    loadScene3d(name).catch((e) => log("3d scene: " + e.message));
  }
}

/** Fetch the parsed URDF link/joint stick figure for a package (2D overlay). */
async function loadUrdfSticks(packageName) {
  const name = packageName || activePkg?.name;
  if (!name) return;
  try {
    urdfSticks = await api("/api/packages/" + encodeURIComponent(name) + "/urdf/sticks");
    log(
      "URDF parsed: " + name + " — " + urdfSticks.link_count + " links, " +
        urdfSticks.joint_count + " joints"
    );
  } catch (e) {
    urdfSticks = null;
    log("URDF parse failed for " + name + ": " + e.message);
  }
}

/** Draw the URDF link graph as simple sticks (base → wheels/links) in robot-local space. */
function drawUrdfSticks(ctx, scale) {
  if (!showSticks || !urdfSticks || !urdfSticks.segments.length) return;
  const roleColor = {
    base: "#3fb950",
    wheel: "#58a6ff",
    lidar: "#f59e0b",
    arm_link: "#a371f7",
    footprint: "#8b949e",
    part: "#c9d1d9",
  };
  ctx.save();
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  urdfSticks.segments.forEach((seg) => {
    ctx.strokeStyle = roleColor[seg.type === "fixed" ? "part" : "wheel"] || "#c9d1d9";
    ctx.beginPath();
    ctx.moveTo(seg.x1 * scale, -seg.y1 * scale);
    ctx.lineTo(seg.x2 * scale, -seg.y2 * scale);
    ctx.stroke();
  });
  urdfSticks.nodes.forEach((n) => {
    ctx.fillStyle = roleColor[n.role] || "#c9d1d9";
    ctx.beginPath();
    ctx.arc(n.x * scale, -n.y * scale, 4, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

async function openPath(rel) {
  const data = await api("/api/files?path=" + encodeURIComponent(rel));
  openFile = rel;
  document.getElementById("tabs").innerHTML =
    `<div class="tab on">${rel}</div>`;
  renderTree(activePkg?.files || []);
  if (editor) {
    const lang = rel.endsWith(".py")
      ? "python"
      : rel.endsWith(".xml") || rel.endsWith(".urdf")
        ? "xml"
        : rel.endsWith(".yaml") || rel.endsWith(".yml")
          ? "yaml"
          : "plaintext";
    monaco.editor.setModelLanguage(editor.getModel(), lang);
    editor.setValue(data.content);
  }
}

async function saveCurrent() {
  if (!openFile || !editor) return;
  await api("/api/files", {
    method: "PUT",
    body: JSON.stringify({ path: openFile, content: editor.getValue() }),
  });
  log("saved " + openFile + " (hot-reload notified)");
}

function setupMonaco() {
  return new Promise((resolve) => {
    require.config({
      paths: { vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.49.0/min/vs" },
    });
    require(["vs/editor/editor.main"], () => {
      editor = monaco.editor.create(document.getElementById("editor"), {
        value: "# Open a demo package to start\n",
        language: "python",
        theme: "vs-dark",
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 13,
        minimap: { enabled: true },
        automaticLayout: true,
        scrollBeyondLastLine: false,
      });
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        saveCurrent().catch((e) => log("save error: " + e.message));
      });
      resolve();
    });
  });
}

function drawRobot(ctx, state, w, h) {
  ctx.clearRect(0, 0, w, h);
  // grid
  ctx.strokeStyle = "#1c2533";
  ctx.lineWidth = 1;
  const step = 40;
  for (let x = 0; x < w; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  // origin
  const cx = w / 2;
  const cy = h / 2;
  const scale = 80;
  const rx = cx + (state.x || 0) * scale;
  const ry = cy - (state.y || 0) * scale;

  trail.push({ x: rx, y: ry });
  if (trail.length > 200) trail.shift();
  ctx.strokeStyle = "#388bfd66";
  ctx.lineWidth = 2;
  ctx.beginPath();
  trail.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
  ctx.stroke();

  // lidar
  if (state.lidar && state.lidar.length) {
    ctx.strokeStyle = "#3fb95033";
    const th0 = state.theta || 0;
    state.lidar.forEach((r, i) => {
      const a = th0 + (i / state.lidar.length) * Math.PI * 2;
      const lx = rx + Math.cos(a) * r * 12;
      const ly = ry - Math.sin(a) * r * 12;
      ctx.beginPath();
      ctx.moveTo(rx, ry);
      ctx.lineTo(lx, ly);
      ctx.stroke();
    });
  }

  const kind = state.kind || "diff_drive_2w";
  ctx.save();
  ctx.translate(rx, ry);
  ctx.rotate(-(state.theta || 0));

  // URDF stick overlay (base + wheels/links parsed from robot.urdf)
  drawUrdfSticks(ctx, scale);

  if (kind === "simple_arm") {
    const j = state.joints || [0.4, -0.6];
    ctx.strokeStyle = "#a371f7";
    ctx.lineWidth = 6;
    ctx.lineCap = "round";
    let x = 0, y = 0;
    const l1 = 50, l2 = 40;
    const x1 = Math.cos(j[0]) * l1;
    const y1 = Math.sin(j[0]) * l1;
    const x2 = x1 + Math.cos(j[0] + j[1]) * l2;
    const y2 = y1 + Math.sin(j[0] + j[1]) * l2;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(x1, -y1);
    ctx.lineTo(x2, -y2);
    ctx.stroke();
    ctx.fillStyle = "#58a6ff";
    [[0, 0], [x1, -y1], [x2, -y2]].forEach(([px, py]) => {
      ctx.beginPath();
      ctx.arc(px, py, 5, 0, Math.PI * 2);
      ctx.fill();
    });
  } else if (kind === "omni_3w") {
    ctx.fillStyle = "#1f6feb";
    ctx.beginPath();
    ctx.arc(0, 0, 18, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#79c0ff";
    for (let i = 0; i < 3; i++) {
      const a = (i * 2 * Math.PI) / 3;
      ctx.beginPath();
      ctx.arc(Math.cos(a) * 16, Math.sin(a) * 16, 5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.strokeStyle = "#fff";
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(24, 0);
    ctx.stroke();
  } else if (kind === "ackermann_4w") {
    ctx.fillStyle = "#d29922";
    ctx.fillRect(-22, -12, 44, 24);
    ctx.fillStyle = "#222";
    [[-14, -14], [-14, 10], [14, -14], [14, 10]].forEach(([wx, wy]) => {
      ctx.fillRect(wx - 4, wy, 8, 4);
    });
    ctx.strokeStyle = "#fff";
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(28, 0);
    ctx.stroke();
  } else if (kind === "tricycle_3w") {
    ctx.fillStyle = "#a371f7";
    ctx.beginPath();
    ctx.moveTo(20, 0);
    ctx.lineTo(-14, 14);
    ctx.lineTo(-14, -14);
    ctx.closePath();
    ctx.fill();
  } else {
    // diff 2w
    ctx.fillStyle = "#3fb950";
    ctx.fillRect(-16, -12, 32, 24);
    ctx.fillStyle = "#111";
    ctx.fillRect(-14, -16, 10, 6);
    ctx.fillRect(-14, 10, 10, 6);
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(22, 0);
    ctx.stroke();
  }
  ctx.restore();

  // HUD
  ctx.fillStyle = "#8b949e";
  ctx.font = "11px JetBrains Mono, monospace";
  ctx.fillText(
    `${kind}  t=${(state.t || 0).toFixed(1)}s  pose=(${(state.x || 0).toFixed(2)}, ${(state.y || 0).toFixed(2)}, ${(state.theta || 0).toFixed(2)})`,
    12,
    18
  );
}

async function tickLoop() {
  const canvas = document.getElementById("viewport");
  const ctx = canvas.getContext("2d");
  // apply keys
  if (simRunning) {
    let lx = parseFloat(document.getElementById("lx").value);
    let ly = parseFloat(document.getElementById("ly").value);
    let az = parseFloat(document.getElementById("az").value);
    if (keys["w"]) lx = 0.6;
    if (keys["s"]) lx = -0.6;
    if (keys["a"]) az = 0.8;
    if (keys["d"]) az = -0.8;
    if (keys["q"]) ly = 0.5;
    if (keys["e"]) ly = -0.5;
    try {
      await api("/api/sim/cmd", {
        method: "POST",
        body: JSON.stringify({ linear_x: lx, linear_y: ly, angular_z: az }),
      });
      const st = await api("/api/sim/state");
      if (viewMode === "2d") {
        drawRobot(ctx, st, canvas.width, canvas.height);
      } else {
        updateRobot3d(st);
        render3d();
      }
      document.getElementById("t-cmd").textContent =
        `lx=${lx.toFixed(2)} ly=${ly.toFixed(2)} az=${az.toFixed(2)}`;
      document.getElementById("t-odom").textContent =
        `x=${(st.x || 0).toFixed(2)} y=${(st.y || 0).toFixed(2)} θ=${(st.theta || 0).toFixed(2)}`;
      document.getElementById("t-scan").textContent =
        st.lidar ? `${st.lidar.length} rays` : "—";
      document.getElementById("sim-meta").textContent =
        (st.mode || "native") + (viewMode === "3d" ? " · 3D" : " · 2D") +
        (st.message ? " · " + st.message : "");
      const status = await api("/api/sim/status");
      document.getElementById("reload-badge").textContent =
        "reloads: " + (status.reload_count || 0);
    } catch (e) {
      /* ignore tick errors when stopped */
    }
  } else if (viewMode === "2d") {
    drawRobot(ctx, { x: 0, y: 0, theta: 0, kind: "diff_drive_2w", lidar: [] }, canvas.width, canvas.height);
  } else {
    render3d();
  }
  requestAnimationFrame(() => setTimeout(tickLoop, 50));
}

/* ---------- WebGL 3D viewer (Three.js) ---------- */

function ensureThree() {
  if (typeof THREE === "undefined") {
    throw new Error("Three.js not loaded");
  }
  if (threeCtx) return threeCtx;
  const host = document.getElementById("viewport3d");
  const w = host.clientWidth || 640;
  const h = host.clientHeight || 400;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.setSize(w, h, false);
  renderer.setClearColor(0x0a0e14, 1);
  host.innerHTML = "";
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0a0e14, 8, 28);
  const camera = new THREE.PerspectiveCamera(50, w / h, 0.02, 80);
  camera.position.set(1.4, 1.1, 1.4);
  camera.lookAt(0, 0.1, 0);

  const amb = new THREE.AmbientLight(0x8899aa, 0.55);
  scene.add(amb);
  const dir = new THREE.DirectionalLight(0xffffff, 0.85);
  dir.position.set(3, 6, 2);
  scene.add(dir);

  // ground grid (XY plane with Z-up: rotate grid)
  const grid = new THREE.GridHelper(6, 24, 0x30363d, 0x21262d);
  grid.rotation.x = Math.PI / 2; // XZ ground with Y-up three default → we use Z-up remap below
  // Three.js is Y-up; our robot is Z-up. We'll map robot Z→Y when placing.
  grid.rotation.x = 0;
  scene.add(grid);
  const axes = new THREE.AxesHelper(0.4);
  scene.add(axes);

  const robot = new THREE.Group();
  scene.add(robot);

  const drag = { active: false, x: 0, y: 0, theta: 0.7, phi: 0.55, dist: 2.2 };
  const canvas = renderer.domElement;
  canvas.addEventListener("pointerdown", (e) => {
    drag.active = true;
    drag.x = e.clientX;
    drag.y = e.clientY;
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointerup", (e) => {
    drag.active = false;
    try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!drag.active) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    drag.x = e.clientX;
    drag.y = e.clientY;
    drag.theta -= dx * 0.01;
    drag.phi = Math.max(0.15, Math.min(1.4, drag.phi + dy * 0.01));
  });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    drag.dist = Math.max(0.6, Math.min(8, drag.dist + e.deltaY * 0.002));
  }, { passive: false });

  threeCtx = { renderer, scene, camera, robot, nodes: {}, drag, host };
  window.addEventListener("resize", () => resize3d());
  return threeCtx;
}

function resize3d() {
  if (!threeCtx) return;
  const { renderer, camera, host } = threeCtx;
  const w = host.clientWidth || 640;
  const h = host.clientHeight || 400;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}

/** Map ROS (x forward, y left, z up) → Three (x right, y up, z toward camera) */
function rosToThree(x, y, z) {
  return new THREE.Vector3(x, z, -y);
}

function parseObjToGeometry(objText) {
  const positions = [];
  const verts = [];
  objText.split("\n").forEach((line) => {
    const t = line.trim();
    if (t.startsWith("v ")) {
      const p = t.split(/\s+/);
      verts.push([parseFloat(p[1]), parseFloat(p[2]), parseFloat(p[3])]);
    } else if (t.startsWith("f ")) {
      const p = t.split(/\s+/).slice(1);
      const idx = p.map((s) => parseInt(s.split("/")[0], 10) - 1);
      // fan triangulate
      for (let i = 1; i + 1 < idx.length; i++) {
        const tri = [idx[0], idx[i], idx[i + 1]];
        tri.forEach((vi) => {
          const v = verts[vi];
          if (!v) return;
          // ROS → Three
          positions.push(v[0], v[2], -v[1]);
        });
      }
    }
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.computeVertexNormals();
  return geo;
}

async function loadScene3d(packageName) {
  ensureThree();
  const name = packageName || activePkg?.name;
  if (!name) return;
  scene3d = await api("/api/packages/" + encodeURIComponent(name) + "/scene3d");
  const { robot } = threeCtx;
  while (robot.children.length) robot.remove(robot.children[0]);
  threeCtx.nodes = {};

  if (!scene3d.nodes || !scene3d.nodes.length) {
    document.getElementById("t-3d").textContent = "no meshes — Build full 3D robot";
    log("3D scene empty for " + name + " — use Models → Build full 3D robot");
    return;
  }

  for (const node of scene3d.nodes) {
    let geo;
    try {
      const objText = await fetch(API + node.mesh_url).then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.text();
      });
      geo = parseObjToGeometry(objText);
    } catch (e) {
      log("mesh load fail " + node.mesh + ": " + e.message);
      geo = new THREE.BoxGeometry(0.1, 0.1, 0.1);
    }
    const role = node.role || "part";
    const color =
      role === "chassis" ? 0x3b82f6 :
      role === "wheel" ? 0x1f2937 :
      role === "lidar" ? 0xf59e0b :
      role === "arm_link" ? 0xa371f7 :
      0x58a6ff;
    const mat = new THREE.MeshStandardMaterial({
      color,
      metalness: 0.25,
      roughness: 0.55,
    });
    const mesh = new THREE.Mesh(geo, mat);
    const g = new THREE.Group();
    // local offset of link relative to base_link (ROS coords → three)
    const [ox, oy, oz] = node.xyz || [0, 0, 0];
    const [rr, rp, ry] = node.rpy || [0, 0, 0];
    const pos = rosToThree(ox, oy, oz);
    g.position.copy(pos);
    // rpy: apply yaw around Three Y (ROS Z)
    g.rotation.order = "YXZ";
    g.rotation.y = ry; // yaw
    g.rotation.x = rp;
    g.rotation.z = -rr;
    const [sx, sy, sz] = node.scale || [1, 1, 1];
    mesh.scale.set(sx, sz, sy);
    g.add(mesh);
    g.userData = { link: node.link, role };
    robot.add(g);
    threeCtx.nodes[node.link] = g;
  }

  document.getElementById("t-3d").textContent =
    `${scene3d.count} links · ${name}`;
  log("3D scene loaded: " + name + " (" + scene3d.count + " nodes)");
  render3d();
}

function updateRobot3d(st) {
  if (!threeCtx) return;
  const { robot, nodes } = threeCtx;
  // base pose on ground plane
  const x = st.x || 0;
  const y = st.y || 0;
  const th = st.theta || 0;
  robot.position.copy(rosToThree(x, y, 0));
  robot.rotation.set(0, th, 0); // yaw about Y (up)

  // wheel spin if joints present
  const joints = st.joints || [];
  const wheelNames = Object.keys(nodes).filter((k) => /wheel/i.test(k));
  wheelNames.forEach((name, i) => {
    const g = nodes[name];
    if (!g || joints[i] === undefined) return;
    // spin about local axis (Three X after ROS Y-axis wheel)
    g.rotation.x = joints[i];
  });
}

function render3d() {
  if (!threeCtx) return;
  const { renderer, scene, camera, drag, robot } = threeCtx;
  // orbit camera around robot
  const target = robot.position.clone().add(new THREE.Vector3(0, 0.12, 0));
  const ct = Math.cos(drag.theta);
  const st = Math.sin(drag.theta);
  const cp = Math.cos(drag.phi);
  const sp = Math.sin(drag.phi);
  camera.position.set(
    target.x + drag.dist * sp * ct,
    target.y + drag.dist * cp,
    target.z + drag.dist * sp * st
  );
  camera.lookAt(target);
  renderer.render(scene, camera);
}

function setViewMode(mode) {
  viewMode = mode;
  document.getElementById("btn-view-2d").classList.toggle("on", mode === "2d");
  document.getElementById("btn-view-3d").classList.toggle("on", mode === "3d");
  document.getElementById("viewport").hidden = mode !== "2d";
  document.getElementById("viewport3d").hidden = mode !== "3d";
  if (mode === "3d") {
    ensureThree();
    resize3d();
    const pkg = activePkg?.name;
    if (pkg) loadScene3d(pkg).catch((e) => log("3d: " + e.message));
  }
}

async function loadRos2Versions() {
  const data = await api("/api/ros2/versions");
  ros2Versions = data.versions || [];
  const sel = document.getElementById("ros2-version");
  sel.innerHTML = "";
  const current = data.selected?.id || "humble";
  ros2Versions.forEach((v) => {
    const o = document.createElement("option");
    o.value = v.id;
    o.textContent = `${v.id} — ${v.name} (${v.status})`;
    if (v.id === current) o.selected = true;
    sel.appendChild(o);
  });
}

async function refreshBundleUi() {
  const pkgs = await api("/api/packages");
  const list = document.getElementById("bundle-pkg-list");
  list.innerHTML = "";
  pkgs.forEach((p) => {
    const lab = document.createElement("label");
    lab.innerHTML = `<input type="checkbox" value="${p.name}" checked /> <span><b>${p.name}</b><br/><span class="muted">${p.files} files</span></span>`;
    list.appendChild(lab);
  });
  const bundles = await api("/api/packages/bundles");
  const bl = document.getElementById("bundle-list");
  bl.innerHTML = "";
  bundles.slice(0, 12).forEach((b) => {
    const d = document.createElement("div");
    d.className = "item";
    d.textContent = `${b.filename} (${Math.round(b.size_bytes / 1024)} KB)`;
    d.title = "Download " + b.filename;
    d.onclick = () => {
      window.open("/api/packages/bundles/" + encodeURIComponent(b.filename), "_blank");
    };
    bl.appendChild(d);
  });
}

async function refreshMeshUi() {
  const presets = await api("/api/models/presets");
  const ps = document.getElementById("mesh-preset");
  if (!ps.options.length) {
    presets.forEach((p) => {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = `${p.id} — ${p.description}`;
      ps.appendChild(o);
    });
  }
  const models = await api("/api/models");
  const ml = document.getElementById("mesh-list");
  ml.innerHTML = "";
  models.forEach((m) => {
    const d = document.createElement("div");
    d.className = "item" + (selectedMeshId === m.id ? " on" : "");
    d.textContent = m.id + (m.meta?.preset ? ` (${m.meta.preset})` : "");
    d.onclick = () => {
      selectedMeshId = m.id;
      refreshMeshUi();
    };
    ml.appendChild(d);
  });
}

function wireUi() {
  document.querySelectorAll(".act").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll(".act").forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("on"));
      document.getElementById("panel-" + btn.dataset.panel).classList.add("on");
      if (btn.dataset.panel === "package") refreshBundleUi().catch((e) => log(e.message));
      if (btn.dataset.panel === "models") refreshMeshUi().catch((e) => log(e.message));
    };
  });

  document.getElementById("ros2-version").onchange = async (e) => {
    const distro = e.target.value;
    try {
      const r = await api("/api/ros2/version", {
        method: "POST",
        body: JSON.stringify({ distro }),
      });
      log("ROS2 target → " + r.selected.id + " (" + r.selected.docker_image + ")");
    } catch (err) {
      log("ros2 version error: " + err.message);
    }
  };

  document.getElementById("btn-bundle").onclick = async () => {
    const boxes = [...document.querySelectorAll("#bundle-pkg-list input:checked")];
    const packages = boxes.map((b) => b.value);
    const distro = document.getElementById("ros2-version").value;
    log("bundling " + packages.join(", ") + " for " + distro + "…");
    try {
      const r = await api("/api/packages/bundle", {
        method: "POST",
        body: JSON.stringify({ packages, distro }),
      });
      log("bundle ok: " + r.filename + " (" + r.size_bytes + " bytes)");
      await refreshBundleUi();
    } catch (e) {
      log("bundle error: " + e.message);
    }
  };

  document.getElementById("btn-mesh-create").onclick = async () => {
    const preset = document.getElementById("mesh-preset").value;
    const name = document.getElementById("mesh-name").value || null;
    try {
      const r = await api("/api/models", {
        method: "POST",
        body: JSON.stringify({ preset, name }),
      });
      selectedMeshId = r.id;
      log("mesh created: " + r.id + " (" + r.bytes + " bytes OBJ)");
      await refreshMeshUi();
    } catch (e) {
      log("mesh error: " + e.message);
    }
  };

  document.getElementById("btn-mesh-attach").onclick = async () => {
    if (!selectedMeshId) {
      log("select a mesh in library first");
      return;
    }
    const packageName = activePkg?.name;
    if (!packageName) {
      log("open a demo package first");
      return;
    }
    try {
      const r = await api("/api/models/attach", {
        method: "POST",
        body: JSON.stringify({
          package: packageName,
          model_id: selectedMeshId,
          auto_fit: true,
          replace: true,
        }),
      });
      log(
        "fit-attached " +
          selectedMeshId +
          " → " +
          packageName +
          (r.fit ? " (auto-fit scale applied)" : "")
      );
      activePkg = await api("/api/workspace");
      renderTree(activePkg.files);
      if (r.urdf) {
        try {
          await openPath("urdf/robot.urdf");
        } catch (_) {}
      }
      if (viewMode === "3d") await loadScene3d(packageName);
    } catch (e) {
      log("attach error: " + e.message);
    }
  };

  document.getElementById("btn-mesh-build").onclick = async () => {
    const packageName = activePkg?.name;
    if (!packageName) {
      log("open a demo package first");
      return;
    }
    log("building full 3D robot for " + packageName + "…");
    try {
      const r = await api("/api/models/build-robot", {
        method: "POST",
        body: JSON.stringify({ package: packageName }),
      });
      log(
        "3D robot ok: " +
          r.links +
          " links · models=" +
          (r.models || []).join(",")
      );
      activePkg = await api("/api/workspace");
      renderTree(activePkg.files);
      try {
        await openPath("urdf/robot.urdf");
      } catch (_) {}
      setViewMode("3d");
      await loadScene3d(packageName);
    } catch (e) {
      log("build-robot error: " + e.message);
    }
  };

  document.getElementById("btn-mesh-reload-scene").onclick = async () => {
    const packageName = activePkg?.name;
    if (!packageName) return;
    setViewMode("3d");
    await loadScene3d(packageName);
  };

  document.getElementById("btn-view-2d").onclick = () => setViewMode("2d");
  document.getElementById("btn-view-3d").onclick = () => setViewMode("3d");
  document.getElementById("btn-sticks").onclick = () => {
    showSticks = !showSticks;
    document.getElementById("btn-sticks").classList.toggle("on", showSticks);
    log("URDF stick overlay " + (showSticks ? "on" : "off"));
  };

  document.getElementById("btn-run").onclick = async () => {
    const demo = activePkg?.name || demos[0]?.name || "diff_drive_2w";
    await api("/api/sim/start", {
      method: "POST",
      body: JSON.stringify({ demo }),
    });
    simRunning = true;
    trail = [];
    setPill("running", "run");
    log("▶ sim " + demo);
  };
  document.getElementById("btn-stop").onclick = async () => {
    await api("/api/sim/stop", { method: "POST" });
    simRunning = false;
    setPill("idle", "idle");
    log("■ stopped");
  };
  document.getElementById("btn-hot").onclick = async () => {
    hotOn = !hotOn;
    document.getElementById("btn-hot").classList.toggle("on", hotOn);
    await api("/api/hot-reload", {
      method: "POST",
      body: JSON.stringify({ enabled: hotOn }),
    });
    log("hot-reload " + (hotOn ? "on" : "off"));
  };
  document.getElementById("btn-zero").onclick = () => {
    document.getElementById("lx").value = 0;
    document.getElementById("ly").value = 0;
    document.getElementById("az").value = 0;
  };
  const refreshDocker = async () => {
    const st = await api("/api/docker/show");
    document.getElementById("docker-info").textContent = JSON.stringify(st, null, 2);
  };
  document.getElementById("btn-docker").onclick = refreshDocker;
  document.getElementById("btn-docker-refresh").onclick = refreshDocker;
  document.getElementById("btn-docker-start").onclick = async () => {
    log("starting docker runtime…");
    try {
      const r = await api("/api/docker/start", { method: "POST" });
      log(JSON.stringify(r).slice(0, 400));
      setPill(r.ok ? "docker" : "idle", r.ok ? "docker" : "idle");
      await refreshDocker();
    } catch (e) {
      log("docker start: " + e.message);
    }
  };

  const canvas = document.getElementById("viewport");
  canvas.addEventListener("keydown", (e) => {
    keys[e.key.toLowerCase()] = true;
  });
  canvas.addEventListener("keyup", (e) => {
    keys[e.key.toLowerCase()] = false;
  });
  window.addEventListener("blur", () => {
    keys = {};
  });
}

async function boot() {
  wireUi();
  await setupMonaco();
  await loadRos2Versions();
  demos = await api("/api/demos");
  renderDemos();
  log("Lappa IDE ready — " + demos.length + " demos · 3D mesh fit v0.3");
  log("Ctrl+S saves file and triggers hot-reload");
  log("Models → Build full 3D robot · toggle 2D/3D in sim panel");
  if (demos[0]) await loadDemo(demos[0].name);
  tickLoop();
  try {
    const d = await api("/api/docker/status");
    log("docker available=" + d.available + " daemon=" + d.daemon + " ros2=" + (d.ros2_distro || "?"));
  } catch (_) {}
}

boot().catch((e) => {
  console.error(e);
  log("boot error: " + e.message);
});

/* --- EN/VI chrome strings --- */
const I18N = {
  en: {
    tag: "ROS2 IDE",
    run: "Start native sim",
    stop: "Stop sim",
    no_pkg: "no package",
    explorer: "Explorer",
    demos: "Robot demos",
    sim: "Sim controls",
    package: "Package / bundle",
    models: "3D models",
    teleop: "Teleop",
    zero: "Zero twist",
    wasd: "WASD / QE also work when canvas focused",
  },
  vi: {
    tag: "IDE gói ROS2",
    run: "Chạy sim offline",
    stop: "Dừng sim",
    no_pkg: "chưa chọn gói",
    explorer: "Thư mục",
    demos: "Robot demo",
    sim: "Điều khiển sim",
    package: "Đóng gói",
    models: "Mô hình 3D",
    teleop: "Teleop",
    zero: "Về 0",
    wasd: "WASD / QE khi focus canvas",
  },
};
let uiLang = localStorage.getItem("lappa_lang") || "en";
function applyI18n() {
  const dict = I18N[uiLang] || I18N.en;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const k = el.getAttribute("data-i18n");
    if (dict[k]) el.textContent = dict[k];
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    const k = el.getAttribute("data-i18n-title");
    if (dict[k]) el.title = dict[k];
  });
  const btn = document.getElementById("btn-lang");
  if (btn) btn.textContent = uiLang === "en" ? "VI" : "EN";
}
document.getElementById("btn-lang")?.addEventListener("click", () => {
  uiLang = uiLang === "en" ? "vi" : "en";
  localStorage.setItem("lappa_lang", uiLang);
  applyI18n();
  log("UI language → " + uiLang);
});
applyI18n();
