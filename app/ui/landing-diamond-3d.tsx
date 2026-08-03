"use client";

import { Environment } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

type Stage = "idle" | "stress1" | "stress2" | "spinning_fast" | "breaking" | "small" | "growing";

type PointerTilt = {
  x: number;
  y: number;
};

type FragmentSeed = {
  id: number;
  position: THREE.Vector3;
  velocity: THREE.Vector3;
  rotation: THREE.Euler;
  rotationVelocity: THREE.Vector3;
  scale: number;
  opacity: number;
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function damp(current: number, target: number, lambda: number, delta: number) {
  return THREE.MathUtils.damp(current, target, lambda, delta);
}

/* Fully-closed 3D Diamond Geometry Generator */
function createClosedDiamondGeometry(scale = 1) {
  const geometry = new THREE.BufferGeometry();

  const crownHeight = 0.35 * scale;
  const pavilionHeight = 0.65 * scale;
  const girdleRadius = 1.0 * scale;
  const tableRadius = 0.58 * scale;
  const tableY = crownHeight;
  const girdleY = 0;
  const cutletY = -pavilionHeight;
  const facets = 12;

  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];

  const addTri = (a: THREE.Vector3, b: THREE.Vector3, c: THREE.Vector3) => {
    const normal = new THREE.Vector3().crossVectors(b.clone().sub(a), c.clone().sub(a)).normalize();
    [a, b, c].forEach((v) => {
      positions.push(v.x, v.y, v.z);
      normals.push(normal.x, normal.y, normal.z);
      uvs.push((v.x / girdleRadius + 1) / 2, (v.z / girdleRadius + 1) / 2);
    });
  };

  for (let i = 0; i < facets; i++) {
    // Table vertices (regular spacing)
    const angleTable0 = (i / facets) * Math.PI * 2;
    const angleTable1 = ((i + 1) / facets) * Math.PI * 2;

    // Girdle vertices (offset by half a segment to create alternating triangles)
    const angleGirdle0 = ((i + 0.5) / facets) * Math.PI * 2;
    const angleGirdle1 = ((i + 1.5) / facets) * Math.PI * 2;

    const tableA = new THREE.Vector3(Math.cos(angleTable0) * tableRadius, tableY, Math.sin(angleTable0) * tableRadius);
    const tableB = new THREE.Vector3(Math.cos(angleTable1) * tableRadius, tableY, Math.sin(angleTable1) * tableRadius);

    const girdleA = new THREE.Vector3(Math.cos(angleGirdle0) * girdleRadius, girdleY, Math.sin(angleGirdle0) * girdleRadius);
    const girdleB = new THREE.Vector3(Math.cos(angleGirdle1) * girdleRadius, girdleY, Math.sin(angleGirdle1) * girdleRadius);

    // Crown facets (alternating triangles with corrected CCW winding order)
    addTri(tableA, tableB, girdleA);       // Points down (CCW: tableA -> tableB -> girdleA)
    addTri(girdleA, tableB, girdleB);      // Points up (CCW: girdleA -> tableB -> girdleB)

    // Pavilion facets (corrected CCW winding order)
    const cutlet = new THREE.Vector3(0, cutletY, 0);
    addTri(girdleA, girdleB, cutlet);      // CCW: girdleA -> girdleB -> cutlet
  }

  // Top Table face (cap) - raised slightly at the center to force EdgesGeometry outlines
  const tableCenter = new THREE.Vector3(0, tableY + 0.06 * scale, 0);
  for (let i = 0; i < facets; i++) {
    const angle0 = (i / facets) * Math.PI * 2;
    const angle1 = ((i + 1) / facets) * Math.PI * 2;
    const tableA = new THREE.Vector3(Math.cos(angle0) * tableRadius, tableY, Math.sin(angle0) * tableRadius);
    const tableB = new THREE.Vector3(Math.cos(angle1) * tableRadius, tableY, Math.sin(angle1) * tableRadius);
    addTri(tableCenter, tableB, tableA);
  }

  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geometry.computeBoundingSphere();
  geometry.computeVertexNormals();

  return geometry;
}

/* Orbiting Light to create premium dynamic specular reflections */
function OrbitingLight({
  color,
  speed,
  radius,
  heightOffset,
  intensity = 6.0,
}: {
  color: string;
  speed: number;
  radius: number;
  heightOffset: number;
  intensity?: number;
}) {
  const lightRef = useRef<THREE.PointLight | null>(null);

  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    const angle = time * speed;
    if (lightRef.current) {
      lightRef.current.position.set(
        Math.cos(angle) * radius,
        heightOffset + Math.sin(time * 0.4) * 0.4,
        Math.sin(angle) * radius
      );
    }
  });

  return <pointLight ref={lightRef} color={color} intensity={intensity} distance={8} />;
}

/* Static vectors to prevent GC allocations in high-frequency frame loops */
const _tempDiff = new THREE.Vector3();
const _tempPush = new THREE.Vector3();
const _tempNudge = new THREE.Vector3();
const _tempTargetMouse = new THREE.Vector3();
const _tempOldPos = new THREE.Vector3();
const _tempVecPedestalMin = new THREE.Vector3(0.001, 0.001, 0.001);
const _tempVecPedestalMax = new THREE.Vector3();

/* Individual Shard Fragment Component (Fully Closed Mini 3D Diamond) */
function FragmentMesh({
  seed,
  draggedIdRef,
  mousePosRef,
  geometry,
  shardPositionsRef,
  fragments,
  xOffset,
  yOffset,
  onDragStart,
  onDragEnd,
}: {
  seed: FragmentSeed;
  draggedIdRef: React.MutableRefObject<number | null>;
  mousePosRef: React.MutableRefObject<THREE.Vector3>;
  geometry: THREE.BufferGeometry;
  shardPositionsRef: React.MutableRefObject<THREE.Vector3[]>;
  fragments: FragmentSeed[];
  xOffset: number;
  yOffset: number;
  onDragStart: () => void;
  onDragEnd: () => void;
}) {
  const meshRef = useRef<THREE.Group>(null);
  const visibleMeshRef = useRef<THREE.Mesh>(null);
  
  const pos = useRef(seed.position.clone());
  const vel = useRef(seed.velocity.clone());
  const rot = useRef(seed.rotation.clone());
  const rotVel = useRef(seed.rotationVelocity.clone());

  useFrame((state, delta) => {
    const mesh = meshRef.current;
    if (!mesh) return;

    const isDragged = draggedIdRef.current === seed.id;

    const responsiveScale = state.size.width < 480 ? 1.05 : state.size.width < 1024 ? 1.10 : 1.05;
    const shardVisualRadius = seed.scale * 0.50 * responsiveScale;

    if (isDragged) {
      _tempOldPos.copy(pos.current);
      
      _tempTargetMouse.copy(mousePosRef.current)
        .setX(mousePosRef.current.x - xOffset)
        .setY(mousePosRef.current.y - yOffset);
        
      pos.current.lerp(_tempTargetMouse, 0.28);
      // Lift the grabbed particle slightly toward the camera (Z axis)
      pos.current.z = damp(pos.current.z, 0.6, 12.0, delta);
      vel.current.copy(pos.current).sub(_tempOldPos).multiplyScalar(1 / Math.max(delta, 0.001));

      // Drag Torque: generate rotational velocity proportional to dragging speed/direction
      // Rotates around axes perpendicular to the movement direction
      rotVel.current.x = damp(rotVel.current.x, -vel.current.y * 1.8, 10.0, delta);
      rotVel.current.y = damp(rotVel.current.y, vel.current.x * 1.8, 10.0, delta);
      rotVel.current.z = damp(rotVel.current.z, (vel.current.x - vel.current.y) * 0.8, 10.0, delta);
    } else {
      // Repulsion from other shards to prevent overlapping/stacking in 3D space
      for (let j = 0; j < shardPositionsRef.current.length; j++) {
        if (j === seed.id) continue;
        const otherPos = shardPositionsRef.current[j];
        if (!otherPos || otherPos.lengthSq() === 0) continue;

        const otherSeed = fragments[j];
        if (!otherSeed) continue;

        // Use pre-allocated temp diff vector
        _tempDiff.copy(pos.current).sub(otherPos);
        const dist = _tempDiff.length();
        const otherVisualRadius = otherSeed.scale * 0.50 * responsiveScale;
        const minDist = (shardVisualRadius + otherVisualRadius) * 1.05; // 5% buffer to prevent clipping
        if (dist < minDist && dist > 0.01) {
          const overlap = minDist - dist;
          const pushStrength = overlap * 6.5;
          
          _tempPush.copy(_tempDiff).normalize().multiplyScalar(pushStrength * delta * 8.0);
          vel.current.add(_tempPush);

          // Positional nudge to resolve overlaps instantly and prevent clipping/merging
          _tempNudge.copy(_tempDiff).normalize().multiplyScalar(overlap * 0.28);
          pos.current.add(_tempNudge);

          // Collision Torque: transfer rotational momentum based on repulsion impact
          const torqueStrength = pushStrength * 0.95;
          rotVel.current.x = (Math.random() - 0.5) * torqueStrength;
          rotVel.current.y = (Math.random() - 0.5) * torqueStrength;
          rotVel.current.z = (Math.random() - 0.5) * torqueStrength;
        }
      }

      // Restore Z-depth to 0 over time so shards fall back to floor plane
      vel.current.z += (0 - pos.current.z) * delta * 2.0;

      // Physics: Apply gravity (y-deceleration)
      vel.current.y -= delta * 7.5;
      
      // Air resistance (damping)
      vel.current.multiplyScalar(0.985);
      
      // Update position
      pos.current.addScaledVector(vel.current, delta);

      // Bounce limits
      const vw = state.viewport.width;
      const vh = state.viewport.height;
      const bounce = 0.65;

      const isMobileOrTablet = state.size.width < 1024;

      // Side boundaries: full screen width for both desktop and mobile
      const worldX = pos.current.x + xOffset;
      const marginX = vw / 2 - shardVisualRadius;
      if (worldX < -marginX) {
        pos.current.x = -marginX - xOffset;
        vel.current.x = -vel.current.x * bounce;
        // Bounce Torque: spin on wall impact
        rotVel.current.y = vel.current.x * 0.8;
        rotVel.current.z = vel.current.y * 0.8;
      } else if (worldX > marginX) {
        pos.current.x = marginX - xOffset;
        vel.current.x = -vel.current.x * bounce;
        // Bounce Torque: spin on wall impact
        rotVel.current.y += vel.current.x * 0.8;
        rotVel.current.z += vel.current.y * 0.8;
      }

      // Vertical boundaries
      const worldY = pos.current.y + yOffset;
      const floorYWorld = -vh / 2 + shardVisualRadius;

      if (isMobileOrTablet) {
        // Mobile/Tablet: bound top at vh * 0.15 to avoid covering text/buttons
        const topCeiling = vh * 0.15;
        if (worldY < floorYWorld) {
          pos.current.y = floorYWorld - yOffset;
          vel.current.y = -vel.current.y * bounce;
          // Friction: high sliding capability so shards slide widely
          vel.current.x *= 0.985;
          vel.current.z *= 0.985;
          
          // Roll Torque: assign sliding linear velocity to rotation!
          rotVel.current.x = vel.current.z * 2.2;
          rotVel.current.z = -vel.current.x * 2.2;
          
          // Higher floor contact rotational friction so tumbles stop
          rotVel.current.multiplyScalar(0.85);
          
          // Add tumbling/shaking on hard impact
          if (Math.abs(vel.current.y) > 0.8) {
            rotVel.current.x = (Math.random() - 0.5) * 4.5;
            rotVel.current.y = (Math.random() - 0.5) * 4.5;
            rotVel.current.z = (Math.random() - 0.5) * 4.5;
          }
        } else if (worldY > topCeiling) {
          pos.current.y = topCeiling - yOffset;
          vel.current.y = -vel.current.y * bounce;
        }
      } else {
        // Desktop: full vertical bounces (no top ceiling, allow full high flying)
        const topCeiling = vh / 2 - shardVisualRadius;
        if (worldY < floorYWorld) {
          pos.current.y = floorYWorld - yOffset;
          vel.current.y = -vel.current.y * bounce;
          // Friction: high sliding capability so shards slide widely across the screen floor
          vel.current.x *= 0.985;
          vel.current.z *= 0.985;
          
          // Roll Torque: assign sliding linear velocity to rotation!
          rotVel.current.x = vel.current.z * 2.2;
          rotVel.current.z = -vel.current.x * 2.2;
          
          // Higher floor contact rotational friction so tumbles stop
          rotVel.current.multiplyScalar(0.85);
          
          // Add tumbling/shaking on hard impact
          if (Math.abs(vel.current.y) > 0.8) {
            rotVel.current.x += (Math.random() - 0.5) * 4.5;
            rotVel.current.y += (Math.random() - 0.5) * 4.5;
            rotVel.current.z += (Math.random() - 0.5) * 4.5;
          }
        } else if (worldY > topCeiling) {
          pos.current.y = topCeiling - yOffset;
          vel.current.y = -vel.current.y * bounce;
        }
      }

      // Z-depth limits
      if (pos.current.z < -2) {
        pos.current.z = -2;
        vel.current.z = -vel.current.z * bounce;
      } else if (pos.current.z > 2) {
        pos.current.z = 2;
        vel.current.z = -vel.current.z * bounce;
      }

      // Let shards rotate freely in 3D using their randomized rotation velocity
      rot.current.x += rotVel.current.x * delta;
      rot.current.y += rotVel.current.y * delta;
      rot.current.z += rotVel.current.z * delta;

      // Rotational damping (air resistance)
      rotVel.current.multiplyScalar(0.985);
    }

    shardPositionsRef.current[seed.id].copy(pos.current);

    mesh.position.set(pos.current.x + xOffset, pos.current.y + yOffset, pos.current.z);
    mesh.rotation.copy(rot.current);

    const visibleMesh = visibleMeshRef.current;
    if (visibleMesh) {
      const material = visibleMesh.material as THREE.MeshPhysicalMaterial;
      if (material) {
        material.emissive.set(isDragged ? "#1643cb" : "#000108");
        material.emissiveIntensity = isDragged ? 2.0 : 0.05;
      }
    }
    
    const grabScaleFactor = isDragged ? 1.35 : 1.0;

    // Heartbeat organic pulse animation - offset phase based on ID
    const phaseOffset = seed.id * 0.15;
    const cycleTime = (state.clock.getElapsedTime() + phaseOffset) % 1.0;
    let thump = 0;
    if (cycleTime < 0.12) {
      thump = Math.sin((cycleTime / 0.12) * Math.PI) * 0.08;
    } else if (cycleTime >= 0.18 && cycleTime < 0.30) {
      thump = Math.sin(((cycleTime - 0.18) / 0.12) * Math.PI) * 0.055;
    }

    mesh.scale.setScalar(seed.scale * 0.58 * responsiveScale * grabScaleFactor * (1.0 + thump));
  });

  const onPointerDown = (e: any) => {
    e.stopPropagation();
    e.target.setPointerCapture(e.pointerId);
    draggedIdRef.current = seed.id;
    onDragStart();
  };

  const onPointerUp = (e: any) => {
    e.stopPropagation();
    e.target.releasePointerCapture(e.pointerId);
    if (draggedIdRef.current === seed.id) {
      draggedIdRef.current = null;
      onDragEnd();
    }
  };

  return (
    <group
      ref={meshRef}
      position={[seed.position.x, seed.position.y, seed.position.z]}
      rotation={seed.rotation}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
    >
      {/* Visible Shard Mesh */}
      <mesh
        ref={visibleMeshRef}
        geometry={geometry}
        castShadow
      >
        <meshPhysicalMaterial
          color="#1643cb"
          transparent={false}
          roughness={1.0}
          metalness={0.0}
          transmission={0.0}
          clearcoat={0.0}
          clearcoatRoughness={1.0}
          polygonOffset
          polygonOffsetFactor={1}
          polygonOffsetUnits={1}
        />
        <lineSegments>
          <edgesGeometry args={[geometry]} />
          <lineBasicMaterial color="#ffffff" transparent opacity={0.8} />
        </lineSegments>
      </mesh>

      {/* Invisible Grab Target (Larger Sphere) */}
      <mesh>
        <sphereGeometry args={[1.8, 8, 8]} />
        <meshBasicMaterial transparent opacity={0.0} depthWrite={false} />
      </mesh>
    </group>
  );
}

function DiamondScene({
  theme,
  stage,
  pointer,
  pointerActive,
  fragments,
  draggedIdRef,
  mousePosRef,
  spinImpulse,
  onDragStart,
  onDragEnd,
}: {
  theme: "light" | "dark";
  stage: Stage;
  pointer: PointerTilt;
  pointerActive: React.MutableRefObject<boolean>;
  fragments: FragmentSeed[];
  draggedIdRef: React.MutableRefObject<number | null>;
  mousePosRef: React.MutableRefObject<THREE.Vector3>;
  spinImpulse: { value: number; time: number };
  onDragStart: () => void;
  onDragEnd: () => void;
}) {
  const { viewport, size, camera } = useThree();

  const isMobile = size.width < 768;
  const isTablet = size.width >= 768 && size.width < 1024;
  
  const xOffset = isMobile || isTablet ? 0 : viewport.width * 0.22;
  const yOffset = isMobile ? -viewport.height * 0.30 : (isTablet ? -viewport.height * 0.26 : 0);

  const responsiveScale = size.width < 480 ? 1.05 : size.width < 1024 ? 1.10 : 1.05;

  const shardPositionsRef = useRef<THREE.Vector3[]>([]);
  if (shardPositionsRef.current.length !== fragments.length) {
    shardPositionsRef.current = Array.from({ length: fragments.length }, () => new THREE.Vector3());
  }

  const groupRef = useRef<THREE.Mesh | null>(null);
  const flashRef = useRef<THREE.PointLight | null>(null);
  const pedestalRef = useRef<THREE.Group | null>(null);

  const autoSpin = useRef(0);
  const currentSpinSpeed = useRef(0.22);
  const tilt = useRef({ x: 0.22, y: 0 });
  const scale = useRef(1);
  
  const flashIntensity = useRef(0);
  const prevStage = useRef(stage);

  // Memoize both the main diamond geometry and the mini-diamond shard geometry
  const mainDiamondGeom = useMemo(() => createClosedDiamondGeometry(0.86), []);
  const miniDiamondGeom = useMemo(() => createClosedDiamondGeometry(0.86), []);

  /* Trigger internal flash light on stage transitions */
  if (stage !== prevStage.current) {
    if (stage === "stress1" || stage === "stress2") {
      flashIntensity.current = 16.0;
    }
    prevStage.current = stage;
  }

  useEffect(() => {
    if (spinImpulse.value > 0) {
      currentSpinSpeed.current = spinImpulse.value;
    }
  }, [spinImpulse]);

  useEffect(() => {
    // Dynamic camera Z adjustments to prevent horizontal clipping in portrait layouts
    const aspect = viewport.aspect;
    camera.position.z = 15 / Math.min(1.0, Math.max(0.45, aspect));
    camera.updateProjectionMatrix();
  }, [viewport.aspect, camera]);

  useFrame((state, delta) => {
    const group = groupRef.current;
    const time = state.clock.getElapsedTime();

    const mouse3D_x = (state.pointer.x * state.viewport.width) / 2;
    const mouse3D_y = (state.pointer.y * state.viewport.height) / 2;
    mousePosRef.current.set(mouse3D_x, mouse3D_y, 0);

    // Apply flash fade
    if (flashRef.current) {
      if (stage === "spinning_fast") {
        // Quick energetic pulse/strobing light right before explosion
        flashRef.current.intensity = 8.0 + Math.sin(time * 50.0) * 6.0;
      } else {
        flashIntensity.current = damp(flashIntensity.current, 0, 8.0, delta);
        flashRef.current.intensity = flashIntensity.current;
      }
    }

    if (pedestalRef.current) {
      pedestalRef.current.rotation.z = time * 0.15;
      if (stage === "breaking") {
        pedestalRef.current.scale.lerp(_tempVecPedestalMin, delta * 7.2);
      } else if (stage === "small") {
        pedestalRef.current.scale.setScalar(0.1 * responsiveScale);
      } else if (stage === "growing") {
        _tempVecPedestalMax.set(responsiveScale, responsiveScale, responsiveScale);
        pedestalRef.current.scale.lerp(_tempVecPedestalMax, delta * 1.65);
      } else {
        _tempVecPedestalMax.set(responsiveScale, responsiveScale, responsiveScale);
        pedestalRef.current.scale.lerp(_tempVecPedestalMax, delta * 3.2);
      }
    }

    if (!group) return;

    // Spin speed: always has a baseline of 0.22 so it rotates continuously when idle
    const isSpinningFast = stage === "spinning_fast";
    const targetSpinSpeed = isSpinningFast ? 16.0 : 0.22;
    const dampingRate = (pointerActive.current || isSpinningFast) ? 4.0 : 2.0;

    // Smoothly interpolate current spin speed to target spin speed
    currentSpinSpeed.current = damp(currentSpinSpeed.current, targetSpinSpeed, dampingRate, delta);

    if (currentSpinSpeed.current > 0.005) {
      autoSpin.current += delta * currentSpinSpeed.current;
    } else {
      // Smoothly return autoSpin to the nearest front-facing angle (multiple of 2*PI)
      const targetAngle = Math.round(autoSpin.current / (Math.PI * 2)) * (Math.PI * 2);
      autoSpin.current = damp(autoSpin.current, targetAngle, 3.0, delta);
    }

    // Pointer-tracking tilt interpolation
    const defaultTiltX = 0.0; // Perfectly upright standing orientation like screenshot 1
    const targetTiltX = pointerActive.current ? -pointer.y * 0.38 + 0.22 : defaultTiltX;
    const targetTiltY = pointerActive.current ? pointer.x * 0.48 : 0;
    tilt.current.x = damp(tilt.current.x, targetTiltX, 4.5, delta);
    tilt.current.y = damp(tilt.current.y, targetTiltY, 4.5, delta);

    group.rotation.x = tilt.current.x;
    group.rotation.y = autoSpin.current + tilt.current.y;
    group.rotation.z = 0;

    // Wobble/shaking animation during high stress stages
    if (stage === "stress2" || stage === "spinning_fast") {
      const shakeAmt = stage === "spinning_fast" ? 0.08 : 0.038;
      group.position.set(
        xOffset + (Math.random() - 0.5) * shakeAmt,
        yOffset + (Math.random() - 0.5) * shakeAmt,
        (Math.random() - 0.5) * shakeAmt
      );
    } else {
      group.position.set(xOffset, yOffset + Math.sin(time * 0.8) * 0.05, 0);
    }

    // Heartbeat organic pulse animation - strobing thump
    let thump = 0;
    if (stage === "idle" || stage === "growing") {
      const cycleTime = time % 1.0;
      if (cycleTime < 0.12) {
        thump = Math.sin((cycleTime / 0.12) * Math.PI) * 0.08;
      } else if (cycleTime >= 0.18 && cycleTime < 0.30) {
        thump = Math.sin(((cycleTime - 0.18) / 0.12) * Math.PI) * 0.055;
      }
    } else if (stage === "stress1") {
      const cycleTime = time % 0.6;
      if (cycleTime < 0.08) {
        thump = Math.sin((cycleTime / 0.08) * Math.PI) * 0.11;
      } else if (cycleTime >= 0.12 && cycleTime < 0.20) {
        thump = Math.sin(((cycleTime - 0.12) / 0.08) * Math.PI) * 0.075;
      }
    } else if (stage === "stress2") {
      const cycleTime = time % 0.35;
      if (cycleTime < 0.06) {
        thump = Math.sin((cycleTime / 0.06) * Math.PI) * 0.15;
      } else if (cycleTime >= 0.09 && cycleTime < 0.15) {
        thump = Math.sin(((cycleTime - 0.09) / 0.06) * Math.PI) * 0.10;
      }
    } else if (stage === "spinning_fast") {
      // Rapid visual vibration heartbeat right before burst
      thump = Math.sin(time * 60.0) * 0.08;
    }

    let baseTargetScale = 1.0;
    if (stage === "small") {
      baseTargetScale = 0.01;
    } else if (stage === "growing") {
      baseTargetScale = 1.0;
    } else if (stage === "breaking" || stage === "spinning_fast") {
      // Scale down during explosion or fast shrink right at the burst transition
      baseTargetScale = stage === "spinning_fast" ? 1.05 : 0.01;
    }

    const targetScaleWithThump = baseTargetScale * (1.0 + thump) * responsiveScale;
    scale.current = damp(scale.current, targetScaleWithThump, 9.5, delta);
    group.scale.setScalar(scale.current);
  });

  const materialProps = useMemo(() => {
    return {
      color: "#1643cb",
      emissive: "#000000",
      emissiveIntensity: 0.0,
      transmission: 0.0,
      roughness: 1.0,
      metalness: 0.0,
      clearcoat: 0.0,
      clearcoatRoughness: 1.0,
      thickness: 0.0,
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    };
  }, []);

  return (
    <>
      <ambientLight intensity={1.1} color="#0c299c" />
      <directionalLight position={[3, 5, 2]} intensity={1.8} color="#1643cb" />
      <directionalLight position={[-3, -3, 2]} intensity={1.0} color="#082073" />
      
      <pointLight ref={flashRef} color="#00f0ff" distance={6} intensity={0} position={[xOffset, yOffset, 1.2]} />

      {/* Holographic Pedestal Base completely removed */}

      {/* Main Core Diamond (Solid Opaque facet geometry) */}
      {stage !== "breaking" && (
        <mesh ref={groupRef} geometry={mainDiamondGeom} castShadow>
          <meshPhysicalMaterial
            {...materialProps}
            ior={2.42}
          />
          <lineSegments>
            <edgesGeometry args={[mainDiamondGeom]} />
            <lineBasicMaterial color="#ffffff" transparent opacity={0.8} />
          </lineSegments>
        </mesh>
      )}

      {/* Shards rendered when shattered (Mini solid closed 3D diamonds) */}
      {stage === "breaking" &&
        fragments.map((seed) => (
          <FragmentMesh
            key={seed.id}
            seed={seed}
            draggedIdRef={draggedIdRef}
            mousePosRef={mousePosRef}
            geometry={miniDiamondGeom}
            shardPositionsRef={shardPositionsRef}
            fragments={fragments}
            xOffset={xOffset}
            yOffset={yOffset}
            onDragStart={onDragStart}
            onDragEnd={onDragEnd}
          />
        ))}

    </>
  );
}

export function LandingDiamond3D() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [stage, setStage] = useState<Stage>("idle");
  const [clicks, setClicks] = useState(0);
  const [isDraggingShard, setIsDraggingShard] = useState(false);
  const [rippleActive, setRippleActive] = useState(false);
  const [pointer, setPointer] = useState<PointerTilt>({ x: 0, y: 0 });
  const [spinImpulse, setSpinImpulse] = useState({ value: 0, time: 0 });

  const containerRef = useRef<HTMLDivElement>(null);
  const pointerActive = useRef(false);
  const draggedIdRef = useRef<number | null>(null);
  const mousePosRef = useRef(new THREE.Vector3());
  const [fragments, setFragments] = useState<FragmentSeed[]>([]);

  const stressResetTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const spinFastTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const breakingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const smallTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const growingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const clearAllTimers = useCallback(() => {
    if (stressResetTimeoutRef.current) clearTimeout(stressResetTimeoutRef.current);
    if (spinFastTimeoutRef.current) clearTimeout(spinFastTimeoutRef.current);
    if (breakingTimeoutRef.current) clearTimeout(breakingTimeoutRef.current);
    if (smallTimeoutRef.current) clearTimeout(smallTimeoutRef.current);
    if (growingTimeoutRef.current) clearTimeout(growingTimeoutRef.current);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const updateTheme = () => {
      const active = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      setTheme(active);
    };
    updateTheme();
    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  // IntersectionObserver to reset the diamond when it is scrolled out of viewport
  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          setStage("idle");
          setClicks(0);
          setFragments([]);
          clearAllTimers();
        }
      });
    }, {
      threshold: 0.0,
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [clearAllTimers]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const handlePointerMove = (e: PointerEvent) => {
      if (e.pointerType === "touch") {
        if (!pointerActive.current) return;
      } else {
        pointerActive.current = true;
      }
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = (e.clientY / window.innerHeight) * 2 - 1;
      
      setPointer({
        x: clamp(x, -1, 1),
        y: clamp(y, -1, 1),
      });
    };

    const handlePointerLeave = () => {
      pointerActive.current = false;
      setPointer({ x: 0, y: 0 });
    };

    const handlePointerDown = () => {
      pointerActive.current = true;
    };

    const handlePointerUp = () => {
      pointerActive.current = false;
    };

    const handlePointerCancel = () => {
      pointerActive.current = false;
      setPointer({ x: 0, y: 0 });
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerleave", handlePointerLeave);
    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerCancel);
    
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerleave", handlePointerLeave);
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerCancel);
    };
  }, []);

  // Shards explosive seed generator
  const generateFragments = () => {
    const shards: FragmentSeed[] = [];
    for (let i = 0; i < 35; i++) {
      const angle = Math.random() * Math.PI * 2;
      // High velocity to explode outward screen-wide
      const horizontalSpeed = Math.random() * 9.0 + 4.0; 
      const velocity = new THREE.Vector3(
        Math.cos(angle) * horizontalSpeed,
        Math.random() * 8.5 + 3.0,
        Math.sin(angle) * horizontalSpeed
      );

      shards.push({
        id: i,
        position: new THREE.Vector3(
          (Math.random() - 0.5) * 0.2,
          (Math.random() - 0.5) * 0.2,
          (Math.random() - 0.5) * 0.2
        ),
        velocity: velocity,
        rotation: new THREE.Euler(
          Math.random() * Math.PI,
          Math.random() * Math.PI,
          Math.random() * Math.PI
        ),
        rotationVelocity: new THREE.Vector3(
          (Math.random() - 0.5) * 6.0,
          (Math.random() - 0.5) * 6.0,
          (Math.random() - 0.5) * 6.0
        ),
        scale: Math.random() * 0.75 + 0.10,
        opacity: 1.0,
      });
    }
    return shards;
  };

  const activate = useCallback(() => {
    // Only allow clicking in normal idle/stress states
    if (stage !== "idle" && stage !== "stress1" && stage !== "stress2") return;

    setClicks((prev) => {
      const nextClicks = prev + 1;

      if (stressResetTimeoutRef.current) clearTimeout(stressResetTimeoutRef.current);

      if (nextClicks === 1) {
        setStage("stress1");
        setSpinImpulse({ value: 2.0, time: Date.now() });
        stressResetTimeoutRef.current = setTimeout(() => {
          setStage("idle");
          setClicks(0);
        }, 3500);
      } else if (nextClicks === 2) {
        setStage("stress2");
        setSpinImpulse({ value: 5.0, time: Date.now() });
        stressResetTimeoutRef.current = setTimeout(() => {
          setStage("idle");
          setClicks(0);
        }, 3500);
      } else if (nextClicks >= 3) {
        clearAllTimers();
        setStage("spinning_fast");
        
        // Spin fast for 1.5 seconds, then explode
        spinFastTimeoutRef.current = setTimeout(() => {
          setStage("breaking");
          setFragments(generateFragments());
          setRippleActive(true);
          const rippleTimeout = setTimeout(() => setRippleActive(false), 900);
        }, 1500);
      }

      return nextClicks;
    });
  }, [stage, clearAllTimers]);

  useEffect(() => {
    const handleDiamondClick = () => {
      activate();
    };
    window.addEventListener("diamond_click", handleDiamondClick);
    return () => {
      window.removeEventListener("diamond_click", handleDiamondClick);
    };
  }, [activate]);

  useEffect(() => {
    return () => {
      clearAllTimers();
    };
  }, [clearAllTimers]);

  return (
    <div
      ref={containerRef}
      className="hero-v2-diamond-shell"
      style={{
        width: "100%",
        height: "100%",
        position: "absolute",
        top: 0,
        left: 0,
        zIndex: stage === "breaking" ? 999 : 2,
        pointerEvents: stage === "breaking" ? "auto" : "none",
        touchAction: stage === "breaking" ? "none" : "auto",
      }}
    >
      {/* Screen-wide ripple light wave effect */}
      {rippleActive && (
        <div
          className="diamond-light-ripple"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 99999,
            pointerEvents: "none",
          }}
        />
      )}

      <Canvas
        className="hero-v2-diamond-canvas"
        shadows={false}
        dpr={Math.min(typeof window !== "undefined" ? window.devicePixelRatio : 1, 1.5)}
        camera={{ position: [0, 0, 15], fov: 9, near: 0.1, far: 100 }}
        gl={{ antialias: true, alpha: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 0.95 }}
        style={{
          background: "transparent",
          width: "100%",
          height: "100%",
          pointerEvents: stage === "breaking" ? "auto" : "none",
          touchAction: isDraggingShard ? "none" : "auto",
        }}
      >
        <DiamondScene
          theme={theme}
          stage={stage}
          pointer={pointer}
          pointerActive={pointerActive}
          fragments={fragments}
          draggedIdRef={draggedIdRef}
          mousePosRef={mousePosRef}
          spinImpulse={spinImpulse}
          onDragStart={() => setIsDraggingShard(true)}
          onDragEnd={() => setIsDraggingShard(false)}
        />
      </Canvas>
    </div>
  );
}
