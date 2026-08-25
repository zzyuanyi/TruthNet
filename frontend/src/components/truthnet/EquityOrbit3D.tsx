import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

export interface OrbitGraphNode {
  id: string;
  name: string;
  entity_type?: string | null;
  risk_level?: string | null;
  wind_code?: string | null;
}

export interface OrbitGraphEdge {
  id?: string;
  source: string;
  target: string;
  relation_type?: string | null;
  ownership_pct?: number | null;
}

interface Props {
  nodes: OrbitGraphNode[];
  edges: OrbitGraphEdge[];
  targetId: string;
  onSelectNode?: (node: OrbitGraphNode) => void;
  height?: number;
}

const TYPE_LABEL: Record<string, string> = {
  person: "自然人",
  company: "企业",
  listed_company: "上市公司",
  branch: "分支机构",
};

const TYPE_COLOR: Record<string, string> = {
  person: "#f5b042",
  company: "#5da2ff",
  listed_company: "#39d4c0",
};

const RISK_COLOR: Record<string, string> = {
  red: "#ff5d5d",
  orange: "#ff9350",
  yellow: "#f5d042",
};

function glowTexture(color: string, core = "rgba(255,255,255,0.95)"): THREE.Texture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 2, size / 2, size / 2, size / 2);
  g.addColorStop(0, core);
  g.addColorStop(0.25, color);
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

function labelTexture(text: string, accent: string): THREE.Texture {
  const canvas = document.createElement("canvas");
  const font = 28;
  const ctx0 = canvas.getContext("2d")!;
  ctx0.font = `600 ${font}px "PingFang SC","Microsoft YaHei",sans-serif`;
  const w = Math.min(320, Math.ceil(ctx0.measureText(text).width) + 24);
  canvas.width = w;
  canvas.height = 46;
  const ctx = canvas.getContext("2d")!;
  ctx.font = `600 ${font}px "PingFang SC","Microsoft YaHei",sans-serif`;
  ctx.textBaseline = "middle";
  ctx.textAlign = "center";
  ctx.shadowColor = "rgba(0,0,0,0.65)";
  ctx.shadowBlur = 6;
  ctx.fillStyle = accent;
  ctx.fillText(text, w / 2, 24);
  return new THREE.CanvasTexture(canvas);
}

interface OrbitBody {
  node: OrbitGraphNode;
  hop: number;
  radius: number;
  angle0: number;
  speed: number;
  size: number;
  color: string;
  maxPct: number | null;
  mesh: THREE.Mesh;
  glow: THREE.Sprite;
  label: THREE.Sprite;
  pivot: THREE.Group;
}

export function EquityOrbit3D({ nodes, edges, targetId, onSelectNode, height = 460 }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const bodiesRef = useRef<OrbitBody[]>([]);
  const nodeMapRef = useRef<Map<string, OrbitGraphNode>>(new Map());
  const [hoverInfo, setHoverInfo] = useState<{ x: number; y: number; node: OrbitGraphNode; pct: number | null } | null>(null);

  // 布局计算：BFS 层级 → 轨道半径 / 行星大小 / 速度
  const layout = useMemo(() => {
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    nodeMapRef.current = nodeMap;
    const adj = new Map<string, { edge: OrbitGraphEdge }[]>();
    for (const e of edges) {
      if (!adj.has(e.source)) adj.set(e.source, []);
      if (!adj.has(e.target)) adj.set(e.target, []);
      adj.get(e.source)!.push({ edge: e });
      adj.get(e.target)!.push({ edge: e });
    }
    // BFS from target
    const hopMap = new Map<string, number>([[targetId, 0]]);
    let frontier = [targetId];
    let hop = 0;
    while (frontier.length > 0) {
      hop += 1;
      const next: string[] = [];
      for (const id of frontier) {
        for (const { edge } of adj.get(id) || []) {
          const other = edge.source === id ? edge.target : edge.source;
          if (!hopMap.has(other)) {
            hopMap.set(other, hop);
            next.push(other);
          }
        }
      }
      frontier = next;
    }
    // 每个节点（非中心）取其所有边中最大持股比例
    const pctMap = new Map<string, number>();
    for (const e of edges) {
      const pct = e.ownership_pct ?? null;
      if (pct == null) continue;
      for (const id of [e.source, e.target]) {
        if (id === targetId) continue;
        pctMap.set(id, Math.max(pctMap.get(id) ?? 0, pct));
      }
    }
    return { hopMap, pctMap };
  }, [nodes, edges, targetId]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || nodes.length === 0) return;

    const isDark = document.documentElement.classList.contains("dark");
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(52, mount.clientWidth / height, 0.1, 400);
    camera.position.set(0, 12, 26);
    camera.lookAt(0, 1, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, height);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, isDark ? 0.55 : 0.85));
    const sun = new THREE.PointLight(0xfff2d8, isDark ? 260 : 160, 120);
    sun.position.set(0, 2, 0);
    scene.add(sun);

    // 星空粒子
    const starCount = 1300;
    const starGeo = new THREE.BufferGeometry();
    const pos = new Float32Array(starCount * 3);
    const col = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      const r = 40 + Math.random() * 70;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.cos(phi) * 0.7;
      pos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
      const warm = Math.random() > 0.82;
      const c = warm ? [1, 0.82, 0.6] : [0.72, 0.85, 1];
      col[i * 3] = c[0];
      col[i * 3 + 1] = c[1];
      col[i * 3 + 2] = c[2];
    }
    starGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    starGeo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const starMat = new THREE.PointsMaterial({
      size: 0.55,
      vertexColors: true,
      transparent: true,
      opacity: isDark ? 0.9 : 0.45,
      sizeAttenuation: true,
    });
    const stars = new THREE.Points(starGeo, starMat);
    scene.add(stars);

    // 中心恒星（标的公司）
    const targetNode = nodeMapRef.current.get(targetId);
    const sunColor = "#ffd98a";
    const sunGroup = new THREE.Group();
    const sunMesh = new THREE.Mesh(
      new THREE.SphereGeometry(2.1, 48, 48),
      new THREE.MeshStandardMaterial({
        color: isDark ? 0xffca6b : 0xffd98a,
        emissive: new THREE.Color(0xffb84d),
        emissiveIntensity: isDark ? 1.35 : 0.9,
        roughness: 0.4,
      }),
    );
    sunGroup.add(sunMesh);
    const sunGlow = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: glowTexture("rgba(255,190,90,0.9)"),
        blending: THREE.AdditiveBlending,
        transparent: true,
        depthWrite: false,
      }),
    );
    sunGlow.scale.set(11, 11, 1);
    sunGroup.add(sunGlow);
    if (targetNode) {
      const lb = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: labelTexture(targetNode.name, isDark ? "#ffe9c2" : "#7a5a1a"), transparent: true, depthWrite: false }),
      );
      lb.scale.set(7.2, 1.03, 1);
      lb.position.set(0, 3.4, 0);
      sunGroup.add(lb);
    }
    scene.add(sunGroup);

    // 轨道环 + 行星
    const bodies: OrbitBody[] = [];
    const ringColor = isDark ? 0x5da2ff : 0x8ab4dd;
    const hopAngles = new Map<number, string[]>();
    for (const n of nodes) {
      const h = layout.hopMap.get(n.id);
      if (h == null || h === 0) continue;
      if (!hopAngles.has(h)) hopAngles.set(h, []);
      hopAngles.get(h)!.push(n.id);
    }
    for (const [h, ids] of hopAngles) {
      const radius = 6.2 + h * 4.1;
      const segs = 128;
      const pts: THREE.Vector3[] = [];
      for (let i = 0; i <= segs; i++) {
        const a = (i / segs) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(a) * radius, 0, Math.sin(a) * radius));
      }
      const ring = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: ringColor, transparent: true, opacity: isDark ? 0.28 : 0.22 }),
      );
      scene.add(ring);
      ids.forEach((id, idx) => {
        const node = nodeMapRef.current.get(id)!;
        const pct = layout.pctMap.get(id) ?? null;
        const color =
          RISK_COLOR[node.risk_level || ""] ?? TYPE_COLOR[node.entity_type || ""] ?? "#5da2ff";
        const size = 0.5 + (pct != null ? Math.sqrt(pct) / 100 * 1.35 : 0.18);
        const angle0 = (idx / ids.length) * Math.PI * 2 + h * 0.9;
        const pivot = new THREE.Group();
        pivot.rotation.y = angle0;
        const mesh = new THREE.Mesh(
          new THREE.SphereGeometry(size, 32, 32),
          new THREE.MeshStandardMaterial({
            color: new THREE.Color(color),
            emissive: new THREE.Color(color),
            emissiveIntensity: isDark ? 0.5 : 0.3,
            roughness: 0.55,
          }),
        );
        mesh.position.set(radius, 0, 0);
        const glow = new THREE.Sprite(
          new THREE.SpriteMaterial({
            map: glowTexture(hexToRgba(color, 0.85)),
            blending: THREE.AdditiveBlending,
            transparent: true,
            depthWrite: false,
          }),
        );
        glow.scale.set(size * 6.4, size * 6.4, 1);
        glow.position.set(radius, 0, 0);
        const label = new THREE.Sprite(
          new THREE.SpriteMaterial({ map: labelTexture(node.name, isDark ? "#e8f1ff" : "#33455c"), transparent: true, depthWrite: false }),
        );
        label.scale.set(Math.min(4.6, 1.15 + node.name.length * 0.34), 0.66, 1);
        label.position.set(radius, size + 0.75, 0);
        pivot.add(mesh, glow, label);
        scene.add(pivot);
        bodies.push({
          node, hop: h, radius, angle0,
          speed: (0.5 / h) * (0.55 + ((idx * 37) % 10) / 18),
          size, color, maxPct: pct,
          mesh, glow, label, pivot,
        });
      });
    }
    bodiesRef.current = bodies;

    // 交互：raycaster hover / click
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let hovered: OrbitBody | null = null;
    const pickables = bodies.map((b) => b.mesh);

    const onPointerMove = (ev: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects([...pickables, sunMesh], false);
      if (hits.length > 0) {
        const obj = hits[0].object;
        renderer.domElement.style.cursor = "pointer";
        if (obj === sunMesh) {
          setHoverInfo({ x: ev.clientX - rect.left, y: ev.clientY - rect.top, node: targetNode!, pct: null });
          hovered = null;
        } else {
          const body = bodies.find((b) => b.mesh === obj) || null;
          hovered = body;
          if (body) {
            setHoverInfo({ x: ev.clientX - rect.left, y: ev.clientY - rect.top, node: body.node, pct: body.maxPct });
          }
        }
      } else {
        renderer.domElement.style.cursor = "grab";
        hovered = null;
        setHoverInfo(null);
      }
    };
    const onClick = () => {
      if (hovered && onSelectNode) onSelectNode(hovered.node);
      else if (onSelectNode && targetNode && hovered === null) {
        // 点击空白不触发；点击恒星 → 打开标的公司
      }
    };
    const onSunClick = () => {
      if (onSelectNode && targetNode) onSelectNode(targetNode);
    };
    renderer.domElement.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("click", onClick);
    sunMesh.addEventListener("click", onSunClick);

    // 动画循环
    let raf = 0;
    const clock = new THREE.Clock();
    const tick = () => {
      const t = clock.getElapsedTime();
      for (const b of bodies) {
        b.pivot.rotation.y = b.angle0 + t * b.speed * 0.42;
      }
      stars.rotation.y = t * 0.008;
      sunMesh.scale.setScalar(1 + Math.sin(t * 1.6) * 0.035);
      (sunGlow.material as THREE.SpriteMaterial).opacity = 0.85 + Math.sin(t * 1.6) * 0.12;
      if (hovered) {
        hovered.mesh.scale.setScalar(1 + Math.sin(t * 6) * 0.12 + 0.15);
      }
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

    const ro = new ResizeObserver(() => {
      if (mount.clientWidth === 0) return;
      camera.aspect = mount.clientWidth / height;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, height);
    });
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("click", onClick);
      scene.traverse((obj) => {
        const any = obj as unknown as { geometry?: THREE.BufferGeometry; material?: THREE.Material | THREE.Material[] };
        any.geometry?.dispose();
        const m = any.material;
        if (Array.isArray(m)) m.forEach((x) => x.dispose());
        else m?.dispose();
      });
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, targetId, layout, height]);

  return (
    <div ref={mountRef} className="relative w-full overflow-hidden rounded-xl" style={{ height }}>
      {hoverInfo && (
        <div
          ref={tooltipRef}
          className="pointer-events-none absolute z-10 rounded-md border border-border/70 bg-card/95 px-2.5 py-1.5 shadow-lg backdrop-blur"
          style={{ left: Math.min(hoverInfo.x + 14, 9999), top: hoverInfo.y + 12, transform: hoverInfo.x > 240 ? "translateX(-110%)" : undefined }}
        >
          <div className="text-xs font-semibold text-foreground">{hoverInfo.node.name}</div>
          <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
            <span>{TYPE_LABEL[hoverInfo.node.entity_type || ""] ?? "主体"}</span>
            {hoverInfo.pct != null && <span className="font-medium text-primary">持股 {hoverInfo.pct}%</span>}
          </div>
          <div className="mt-0.5 text-[10px] text-muted-foreground/80">点击查看详情 →</div>
        </div>
      )}
      {nodes.length <= 1 && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
          暂无股权关系数据
        </div>
      )}
    </div>
  );
}

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
