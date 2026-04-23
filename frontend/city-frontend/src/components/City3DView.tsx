import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { ExpansionRecord, Network, TrafficLight, Vehicle, Zone } from '../types';
import { buildPhysicalRoads } from '../utils/physicalRoads';
import { createSceneTransform, getNetworkBounds } from '../utils/worldTransform';

interface City3DViewProps {
  network: Network | null;
  zones: Zone[];
  vehicles: Vehicle[];
  trafficLights: TrafficLight[];
  expansionHistory: ExpansionRecord[];
}

const createScene = (container: HTMLDivElement) => {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xdff1ff);
  scene.fog = new THREE.Fog(0xdff1ff, 90, 220);

  const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 500);
  camera.position.set(0, 85, 120);

  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
  scene.add(ambientLight);

  const sun = new THREE.DirectionalLight(0xfff0d6, 1.15);
  sun.position.set(-80, 120, -40);
  sun.castShadow = true;
  sun.shadow.mapSize.width = 2048;
  sun.shadow.mapSize.height = 2048;
  scene.add(sun);

  const fill = new THREE.DirectionalLight(0xcfe7ff, 0.35);
  fill.position.set(70, 60, 50);
  scene.add(fill);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 20;
  controls.maxDistance = 260;
  controls.maxPolarAngle = Math.PI / 2.05;
  controls.target.set(0, 0, 0);

  return { scene, camera, renderer, controls };
};

const disposeMesh = (object: THREE.Object3D) => {
  const mesh = object as THREE.Mesh;
  if (mesh.geometry) {
    mesh.geometry.dispose();
  }
  if (Array.isArray(mesh.material)) {
    mesh.material.forEach(material => material.dispose());
  } else if (mesh.material) {
    mesh.material.dispose();
  }
};

const clearCityObjects = (scene: THREE.Scene) => {
  for (let i = scene.children.length - 1; i >= 0; i -= 1) {
    const child = scene.children[i];
    if (child.userData.dynamicCityObject) {
      scene.remove(child);
      disposeMesh(child);
    }
  }
};

const markDynamic = <T extends THREE.Object3D>(object: T): T => {
  object.userData.dynamicCityObject = true;
  return object;
};

const getDirectionalSignalState = (
  light: TrafficLight,
  direction: 'ns' | 'ew'
): 'RED' | 'YELLOW' | 'GREEN' => {
  const directional = direction === 'ns' ? light.ns_state : light.ew_state;
  return directional || light.state || 'RED';
};

const getSignalColor = (state: 'RED' | 'YELLOW' | 'GREEN') => {
  if (state === 'GREEN') return 0x22c55e;
  if (state === 'YELLOW') return 0xeab308;
  return 0xdc2626;
};

const addRoadSegmentMesh = (
  scene: THREE.Scene,
  start: { x: number; z: number },
  end: { x: number; z: number },
  width: number,
  material: THREE.Material,
  name: string
) => {
  const dx = end.x - start.x;
  const dz = end.z - start.z;
  const len = Math.hypot(dx, dz);
  if (len < 0.01) return;
  const angle = Math.atan2(dz, dx);
  const mesh = markDynamic(new THREE.Mesh(new THREE.BoxGeometry(len, 0.06, width), material));
  mesh.position.set((start.x + end.x) / 2, -0.01, (start.z + end.z) / 2);
  mesh.rotation.y = angle;
  mesh.receiveShadow = true;
  mesh.name = name;
  scene.add(mesh);
};

const clipRoadEndpoints3D = (
  start: { x: number; z: number },
  end: { x: number; z: number },
  startInset: number,
  endInset: number
) => {
  const dx = end.x - start.x;
  const dz = end.z - start.z;
  const len = Math.hypot(dx, dz);
  if (len < 0.001) {
    return { start, end, len };
  }

  const ux = dx / len;
  const uz = dz / len;
  const clippedStart = {
    x: start.x + ux * Math.min(startInset, len * 0.3),
    z: start.z + uz * Math.min(startInset, len * 0.3),
  };
  const clippedEnd = {
    x: end.x - ux * Math.min(endInset, len * 0.3),
    z: end.z - uz * Math.min(endInset, len * 0.3),
  };

  return { start: clippedStart, end: clippedEnd, len: Math.hypot(clippedEnd.x - clippedStart.x, clippedEnd.z - clippedStart.z) };
};

const renderRoadNetwork = (
  network: Network,
  scene: THREE.Scene,
  worldToScene: (x: number, y: number) => { x: number; z: number },
  expansionHistory: ExpansionRecord[]
) => {
  const roadMaterial = new THREE.MeshStandardMaterial({
    color: 0x424852,
    roughness: 0.96,
    metalness: 0.04
  });
  const laneMaterial = new THREE.MeshStandardMaterial({
    color: 0xf5f3d7,
    roughness: 0.8,
    metalness: 0.02
  });
  const centerDividerMaterial = new THREE.MeshStandardMaterial({
    color: 0xf8fafc,
    roughness: 0.82,
    metalness: 0.02
  });
  const junctionMaterial = new THREE.MeshStandardMaterial({
    color: 0x555d68,
    roughness: 0.92,
    metalness: 0.04
  });

  const nodeById = new Map(network.nodes.map(node => [node.id, node]));
  const nodeRadiusHint = new Map<string, number>();
  const expandedNodeIds = new Set(
    expansionHistory
      .filter(record => record.type === 'add_node' && record.node_id)
      .map(record => record.node_id as string)
  );
  const physicalRoads = buildPhysicalRoads(network);

  physicalRoads.forEach(road => {
    const roadWidth = 0.34 + Math.max(0, road.totalLanes - 1) * 0.11;
    const hintRadius = Math.max(0.4, roadWidth * 0.42);
    nodeRadiusHint.set(road.fromNodeId, Math.max(nodeRadiusHint.get(road.fromNodeId) || 0, hintRadius));
    nodeRadiusHint.set(road.toNodeId, Math.max(nodeRadiusHint.get(road.toNodeId) || 0, hintRadius));
  });

  physicalRoads.forEach(road => {
    const fromNode = nodeById.get(road.fromNodeId);
    const toNode = nodeById.get(road.toNodeId);
    if (!fromNode || !toNode) return;

    const p1 = worldToScene(fromNode.x, fromNode.y);
    const p2 = worldToScene(toNode.x, toNode.y);
    const roadWidth = 0.34 + Math.max(0, road.totalLanes - 1) * 0.11;
    const clipped = clipRoadEndpoints3D(
      p1,
      p2,
      nodeRadiusHint.get(road.fromNodeId) || roadWidth * 0.55,
      nodeRadiusHint.get(road.toNodeId) || roadWidth * 0.55
    );
    if (clipped.len < 0.01) return;
    const dx = clipped.end.x - clipped.start.x;
    const dz = clipped.end.z - clipped.start.z;
    const len = clipped.len;
    const angle = Math.atan2(dz, dx);

    addRoadSegmentMesh(scene, clipped.start, clipped.end, roadWidth, roadMaterial, 'Road');

    if (road.reverseLanes > 0) {
      addRoadSegmentMesh(scene, clipped.start, clipped.end, Math.max(0.08, roadWidth * 0.08), centerDividerMaterial, 'RoadDivider');
    }

    if (road.reverseLanes === 0 && road.totalLanes > 1) {
      for (let dividerIndex = 1; dividerIndex < road.totalLanes; dividerIndex += 1) {
        const laneOffset = (dividerIndex - road.totalLanes / 2) * (roadWidth / road.totalLanes);
        const laneMark = markDynamic(
          new THREE.Mesh(new THREE.BoxGeometry(Math.max(0.2, len * 0.96), 0.01, 0.04), laneMaterial)
        );
        laneMark.position.set(
          (clipped.start.x + clipped.end.x) / 2 - Math.sin(angle) * laneOffset,
          0.025,
          (clipped.start.z + clipped.end.z) / 2 + Math.cos(angle) * laneOffset
        );
        laneMark.rotation.y = angle;
        laneMark.receiveShadow = true;
        laneMark.name = 'Road';
        scene.add(laneMark);
      }
    }
  });

  network.nodes.forEach(node => {
    const p = worldToScene(node.x, node.y);
    const radius = Math.max(0.28, nodeRadiusHint.get(node.id) || 0.28);
    const junction = markDynamic(
      new THREE.Mesh(
        new THREE.CylinderGeometry(expandedNodeIds.has(node.id) ? radius * 1.1 : radius, expandedNodeIds.has(node.id) ? radius * 1.1 : radius, 0.08, 20),
        junctionMaterial
      )
    );
    junction.position.set(p.x, -0.01, p.z);
    junction.receiveShadow = true;
    junction.name = 'Road';
    scene.add(junction);
  });
};

const createLabelSprite = (text: string, color = '#111111', bg = 'rgba(255,255,255,0)') => {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 72;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return null;
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (bg !== 'rgba(255,255,255,0)') {
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
  ctx.fillStyle = color;
  ctx.font = '28px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text.slice(0, 18), canvas.width / 2, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = markDynamic(new THREE.Sprite(material));
  sprite.scale.set(5.8, 1.6, 1);
  return sprite;
};

const renderZones = (
  zones: Zone[],
  network: Network,
  scene: THREE.Scene,
  worldToScene: (x: number, y: number) => { x: number; z: number },
  sceneScale: number
) => {
  const nodeById = new Map(network.nodes.map(node => [node.id, node]));
  const roadBuffers = network.edges
    .map(edge => {
      const fromNode = nodeById.get(edge.from_node);
      const toNode = nodeById.get(edge.to_node);
      if (!fromNode || !toNode) return null;
      return {
        minX: Math.min(fromNode.x, toNode.x) - 18,
        maxX: Math.max(fromNode.x, toNode.x) + 18,
        minY: Math.min(fromNode.y, toNode.y) - 18,
        maxY: Math.max(fromNode.y, toNode.y) + 18
      };
    })
    .filter(Boolean) as Array<{ minX: number; maxX: number; minY: number; maxY: number }>;

  const materials: Record<string, THREE.MeshStandardMaterial> = {
    RESIDENTIAL: new THREE.MeshStandardMaterial({ color: 0xd6eaff, roughness: 0.88 }),
    COMMERCIAL: new THREE.MeshStandardMaterial({ color: 0xf8d4aa, roughness: 0.85 }),
    INDUSTRIAL: new THREE.MeshStandardMaterial({ color: 0xb8c3cf, roughness: 0.92 }),
    HOSPITAL: new THREE.MeshStandardMaterial({ color: 0xf6c7cc, roughness: 0.86 }),
    SCHOOL: new THREE.MeshStandardMaterial({ color: 0xcfeeb8, roughness: 0.86 }),
    PARK: new THREE.MeshStandardMaterial({ color: 0x90d48d, roughness: 1 }),
    OFFICE: new THREE.MeshStandardMaterial({ color: 0xdcccf7, roughness: 0.86 }),
    MIXED_USE: new THREE.MeshStandardMaterial({ color: 0xf4c6df, roughness: 0.86 }),
    GOVERNMENT: new THREE.MeshStandardMaterial({ color: 0xc4ece6, roughness: 0.86 }),
    SHOPPING: new THREE.MeshStandardMaterial({ color: 0xf8eb99, roughness: 0.82 })
  };

  zones.forEach((zone, index) => {
    const zoneCenterX = zone.center_x;
    const zoneCenterY = zone.center_y;

    const overlapsRoad = roadBuffers.some(buffer => {
      return (
        zoneCenterX >= buffer.minX &&
        zoneCenterX <= buffer.maxX &&
        zoneCenterY >= buffer.minY &&
        zoneCenterY <= buffer.maxY
      );
    });

    if (overlapsRoad) {
      return;
    }

    const footprintWidth = Math.max(1.4, zone.width * sceneScale * 0.18);
    const footprintDepth = Math.max(1.4, zone.height * sceneScale * 0.18);
    const { x, z } = worldToScene(zoneCenterX, zoneCenterY);
    const height = zone.zone_type === 'PARK' ? 0.2 : 2.8 + (index % 5) * 1.3;
    const material = materials[zone.zone_type] || new THREE.MeshStandardMaterial({ color: 0xd7dde5, roughness: 0.9 });

    const geometry =
      zone.zone_type === 'PARK'
        ? new THREE.BoxGeometry(footprintWidth, 0.08, footprintDepth)
        : new THREE.BoxGeometry(footprintWidth, height, footprintDepth);
    const building = markDynamic(new THREE.Mesh(geometry, material));
    building.position.set(x, zone.zone_type === 'PARK' ? 0.02 : height / 2, z);
    building.castShadow = zone.zone_type !== 'PARK';
    building.receiveShadow = true;
    building.name = zone.zone_type === 'PARK' ? 'Grass' : 'Building';
    scene.add(building);

    const label = createLabelSprite(zone.name || zone.zone_type_display || zone.zone_type, '#111111', 'rgba(255,255,255,0)');
    if (label) {
      label.position.set(x, Math.max(1.6, height + 0.9), z);
      label.name = 'ZoneLabel';
      scene.add(label);
    }
  });
};

const renderVehicles = (
  vehicles: Vehicle[],
  scene: THREE.Scene,
  worldToScene: (x: number, y: number) => { x: number; z: number }
) => {
  const vehicleMaterial = new THREE.MeshStandardMaterial({
    color: 0x22c55e,
    roughness: 0.7,
    metalness: 0.08
  });

  vehicles.forEach(vehicle => {
    const { x, z } = worldToScene(vehicle.x, vehicle.y);
    const heading = Number.isFinite(vehicle.direction) ? vehicle.direction : 0;
    const body = markDynamic(new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.45, 0.55), vehicleMaterial));
    body.position.set(x, 0.22, z);
    body.rotation.y = -heading;
    body.castShadow = true;
    body.receiveShadow = true;
    body.name = 'Vehicle';
    scene.add(body);
  });
};

const renderTrafficLights = (
  trafficLights: TrafficLight[],
  network: Network,
  scene: THREE.Scene,
  worldToScene: (x: number, y: number) => { x: number; z: number }
) => {
  const nodeById = new Map(network.nodes.map(node => [node.id, node]));

  trafficLights.forEach(light => {
    const node = nodeById.get(light.node_id);
    if (!node) return;
    const poleMaterial = new THREE.MeshStandardMaterial({ color: 0x374151, roughness: 0.95 });
    const arrowShape = new THREE.ConeGeometry(0.11, 0.3, 10);
    const nodePoint = worldToScene(node.x, node.y);

    const addDirectionalSignal = (
      positionX: number,
      positionZ: number,
      rotationX: number,
      rotationZ: number,
      lampColor: number
    ) => {
      const pole = markDynamic(new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.95, 8), poleMaterial));
      pole.position.set(positionX, 0.48, positionZ);
      pole.name = 'TrafficLight';
      scene.add(pole);

      const lamp = markDynamic(
        new THREE.Mesh(
          new THREE.SphereGeometry(0.1, 12, 12),
          new THREE.MeshStandardMaterial({ color: lampColor, emissive: lampColor, emissiveIntensity: 0.7 })
        )
      );
      lamp.position.set(positionX, 1.02, positionZ);
      lamp.name = 'TrafficLight';
      scene.add(lamp);

      const arrow = markDynamic(
        new THREE.Mesh(
          arrowShape,
          new THREE.MeshStandardMaterial({ color: lampColor, emissive: lampColor, emissiveIntensity: 0.35 })
        )
      );
      arrow.position.set(positionX, 1.28, positionZ);
      arrow.rotation.x = rotationX;
      arrow.rotation.z = rotationZ;
      arrow.name = 'TrafficLight';
      scene.add(arrow);
    };

    addDirectionalSignal(
      nodePoint.x - 0.18,
      nodePoint.z,
      Math.PI / 2,
      0,
      getSignalColor(getDirectionalSignalState(light, 'ns'))
    );
    addDirectionalSignal(
      nodePoint.x + 0.18,
      nodePoint.z,
      Math.PI / 2,
      Math.PI / 2,
      getSignalColor(getDirectionalSignalState(light, 'ew'))
    );
  });
};

export const City3DView: React.FC<City3DViewProps> = ({ network, zones, vehicles, trafficLights, expansionHistory }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const animationRef = useRef<number | null>(null);
  const hasInitializedCameraRef = useRef(false);
  const [isReady, setIsReady] = useState(false);

  const layoutKey = useMemo(() => {
    if (!network) return 'none';
    const nodeSig = network.nodes
      .map(node => `${node.id}:${Math.round(node.x)}:${Math.round(node.y)}`)
      .sort()
      .join('|');
    const edgeSig = network.edges
      .map(edge => `${edge.id}:${edge.from_node}->${edge.to_node}:${edge.num_lanes}`)
      .sort()
      .join('|');
    const zoneSig = zones
      .map(zone => `${zone.zone_id}:${zone.zone_type}:${Math.round(zone.center_x)}:${Math.round(zone.center_y)}`)
      .sort()
      .join('|');
    return `${nodeSig}#${edgeSig}#${zoneSig}`;
  }, [network, zones]);

  useEffect(() => {
    if (!containerRef.current) return;

    const { scene, camera, renderer, controls } = createScene(containerRef.current);
    sceneRef.current = scene;
    cameraRef.current = camera;
    rendererRef.current = renderer;
    controlsRef.current = controls;

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      animationRef.current = requestAnimationFrame(animate);
    };
    animate();

    const resize = () => {
      if (!containerRef.current || !cameraRef.current || !rendererRef.current) return;
      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;
      cameraRef.current.aspect = width / Math.max(1, height);
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(width, height);
    };

    const observer = new ResizeObserver(resize);
    observer.observe(containerRef.current);
    resize();
    setIsReady(true);

    return () => {
      observer.disconnect();
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      controls.dispose();
      clearCityObjects(scene);
      renderer.dispose();
      if (renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
    };
  }, []);

  useEffect(() => {
    if (!isReady || !sceneRef.current || !network || !cameraRef.current || !controlsRef.current) {
      return;
    }

    const scene = sceneRef.current;
    clearCityObjects(scene);

    const bounds = getNetworkBounds(network, { zones, padding: 20 });
    const sceneTransform = createSceneTransform(bounds, 100);

    const worldToScene = (wx: number, wy: number) => ({
      x: (wx - sceneTransform.centerX) * sceneTransform.scale,
      // Three.js 场景采用与 2D 视图一致的 Y 轴翻转约定，避免道路与朝向错位。
      z: -(wy - sceneTransform.centerY) * sceneTransform.scale
    });

    const ground = markDynamic(
      new THREE.Mesh(
        new THREE.PlaneGeometry(bounds.width * sceneTransform.scale * 1.25, bounds.height * sceneTransform.scale * 1.25),
        new THREE.MeshStandardMaterial({ color: 0x80ad67, roughness: 1 })
      )
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.08;
    ground.receiveShadow = true;
    ground.name = 'ForestGround';
    scene.add(ground);

    renderRoadNetwork(network, scene, worldToScene, expansionHistory);
    renderZones(zones, network, scene, worldToScene, sceneTransform.scale);
    renderVehicles(vehicles, scene, worldToScene);
    renderTrafficLights(trafficLights, network, scene, worldToScene);

    if (!hasInitializedCameraRef.current) {
      const longestSpan = Math.max(bounds.width, bounds.height) * sceneTransform.scale;
      cameraRef.current.position.set(longestSpan * 0.25, Math.max(48, longestSpan * 0.95), Math.max(60, longestSpan * 0.95));
      controlsRef.current.target.set(0, 0, 0);
      controlsRef.current.update();
      hasInitializedCameraRef.current = true;
    }
  }, [expansionHistory, isReady, layoutKey, network, trafficLights, vehicles, zones]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        background: 'linear-gradient(180deg, #cfe8fb 0%, #edf8ff 58%, #f6fff3 100%)',
        borderRadius: 12,
        overflow: 'hidden'
      }}
    />
  );
};

export default City3DView;
