"use strict";

const layout = JSON.parse(document.querySelector("#layout").textContent);
const startCard = document.querySelector("#start");
const play = document.querySelector("#play");
const hint = document.querySelector("#hint");
const crosshair = document.querySelector("#crosshair");
const radians = Math.PI / 180;
const CHILD_MESH = "Player character";
const cryDuration = 4;
const residentCryDuration = 15;
const smooth01 = t => {
    const u = Math.max(0, Math.min(1, t));
    return u * u * (3 - 2 * u);
};

function createSky(scene) {
    const sky = new THREE.Mesh(new THREE.SphereGeometry(100, 28, 16), new THREE.ShaderMaterial({
        side: THREE.BackSide,
        depthWrite: false,
        vertexShader: `
            varying vec3 viewDirection;
            void main() {
                viewDirection = position;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.);
            }
        `,
        fragmentShader: `
            varying vec3 viewDirection;
            void main() {
                vec3 d = normalize(viewDirection);
                float altitude = smoothstep(-.07, .72, d.y);
                vec3 low = vec3(.745, .800, .716);
                vec3 high = vec3(.55, .70, .73);
                vec3 color = mix(low, high, altitude);
                vec3 sun = normalize(vec3(-.69,.58,.43));
                float facing = max(dot(d, sun), 0.);
                color += vec3(.25,.17,.08) * pow(facing, 9.) * .60;
                color = mix(color, vec3(1., .93, .73), smoothstep(.99952, .99984, facing));
                gl_FragColor = vec4(color, 1.);
            }
        `,
    }));
    sky.frustumCulled = false;
    sky.renderOrder = -1;
    scene.add(sky);
    return sky;
}

async function loadMeshes() {
    const raw = atob(document.querySelector("#mesh-data").textContent.trim());
    const bytes = Uint8Array.from(raw, char => char.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    const data = new DataView(await new Response(stream).arrayBuffer());
    if (data.getUint32(0) !== 0x43444835) throw new Error("Invalid village mesh header");
    const result = new Map();
    const color = new THREE.Color();
    const count = data.getUint16(4, true);
    let offset = 6;

    for (let mesh = 0; mesh < count; mesh++) {
        const nameLength = data.getUint8(offset++);
        let name = "";
        for (let n = 0; n < nameLength; n++) name += String.fromCharCode(data.getUint8(offset++));
        const vertices = data.getUint32(offset, true);
        offset += 4;
        const points = new Float32Array(vertices * 3);
        const colors = new Float32Array(vertices * 3);
        const skinned = name === CHILD_MESH || name.startsWith("Resident ");
        const unit = skinned ? .001 : .01;
        const uv = name === "Auto panels" || name.startsWith("House skin ") ? new Float32Array(vertices * 2) : null;
        const normals = skinned ? new Float32Array(vertices * 3) : null;
        const skinIndex = skinned ? new Uint16Array(vertices * 4) : null;
        const skinWeight = skinned ? new Float32Array(vertices * 4) : null;

        for (let n = 0; n < vertices; n++) {
            // Mirror Unity's forward axis and reverse the winding.
            const i = (n - n % 3 + (3 - n % 3) % 3) * 3;
            points[i] = data.getInt16(offset, true) * unit;
            points[i + 1] = data.getInt16(offset + 2, true) * unit;
            points[i + 2] = -data.getInt16(offset + 4, true) * unit;
            color.setRGB(data.getUint8(offset + 6) / 255, data.getUint8(offset + 7) / 255,
                data.getUint8(offset + 8) / 255, THREE.SRGBColorSpace);
            colors.set([color.r, color.g, color.b], i);
            offset += 9;
            if (uv) {
                uv[2 * i / 3] = data.getUint16(offset, true) / 65535;
                uv[2 * i / 3 + 1] = data.getUint16(offset + 2, true) / 65535;
                offset += 4;
            }
            if (skinned) {
                const nx = data.getInt8(offset);
                const ny = data.getInt8(offset + 1);
                const nz = -data.getInt8(offset + 2);
                const length = Math.hypot(nx, ny, nz) || 1;
                normals.set([nx / length, ny / length, nz / length], i);
                const joint = 4 * i / 3;
                skinIndex[joint] = data.getUint8(offset + 3);
                skinIndex[joint + 1] = data.getUint8(offset + 4);
                skinWeight[joint] = data.getUint8(offset + 5) / 255;
                skinWeight[joint + 1] = 1 - skinWeight[joint];
                offset += 6;
            }
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.BufferAttribute(points, 3));
        geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
        if (uv) geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
        if (skinned) {
            geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
            geometry.setAttribute("skinIndex", new THREE.BufferAttribute(skinIndex, 4));
            geometry.setAttribute("skinWeight", new THREE.BufferAttribute(skinWeight, 4));
        } else {
            geometry.computeVertexNormals();
        }
        result.set(name, geometry);
    }
    if (offset !== data.byteLength) throw new Error("Trailing mesh data");
    return result;
}

function carPaintMaterial() {
    const material = new THREE.MeshLambertMaterial({vertexColors: true});
    material.customProgramCacheKey = () => "car";
    material.onBeforeCompile = shader => {
        shader.vertexShader = "varying vec3 vSurfacePosition;\n" + shader.vertexShader.replace(
            "#include <project_vertex>",
            "#include <project_vertex>\n vSurfacePosition = (modelMatrix * vec4(transformed, 1.)).xyz;");
        shader.fragmentShader = "varying vec3 vSurfacePosition;\n" + shader.fragmentShader.replace(
            "#include <color_fragment>", `#include <color_fragment>
                vec3 p = vSurfacePosition;
                float mottling = sin(31.*p.x+17.*p.z+11.*p.y)*sin(25.*p.z-19.*p.y);
                float detail = .92+.08*clamp(p.y,0.,1.)+.039*mottling*(1.-clamp(length(fwidth(p))*13.,0.,1.));
                diffuseColor.rgb *= detail;`);
    };
    return material;
}

function terrainAtlas(selector, size, vertexColors) {
    const data = Uint8Array.from(atob(document.querySelector(selector).textContent.trim()), byte => byte.charCodeAt(0));
    const atlas = new THREE.DataTexture(data, size, size);
    atlas.colorSpace = THREE.SRGBColorSpace;
    atlas.generateMipmaps = true;
    atlas.magFilter = THREE.LinearFilter;
    atlas.minFilter = THREE.LinearMipmapLinearFilter;
    atlas.needsUpdate = true;
    return new THREE.MeshLambertMaterial({map: atlas, vertexColors});
}

function collisionBox(box) {
    const [x, y, z, w, h, d] = box;
    return new THREE.Box3(new THREE.Vector3(x - w / 2, y - h / 2, -z - d / 2),
        new THREE.Vector3(x + w / 2, y + h / 2, -z + d / 2));
}

function circleHitsBox(x, z, b, radius) {
    const dx = x - THREE.MathUtils.clamp(x, b.min.x, b.max.x);
    const dz = z - THREE.MathUtils.clamp(z, b.min.z, b.max.z);
    return dx * dx + dz * dz < radius * radius;
}

function gateClearance(gate, player, angle) {
    const dx = player.x - gate.pivot.position.x;
    const dz = player.z - gate.pivot.position.z;
    const x = Math.cos(angle);
    const z = Math.sin(angle);
    const t = THREE.MathUtils.clamp(dx * x + dz * z, 0, gate.width);
    return (dx - x * t) ** 2 + (dz - z * t) ** 2;
}

function rigPerson(player, geometry, material, rig, name, pace = rig) {
    const model = new THREE.SkinnedMesh(geometry, material);
    model.name = name;
    model.castShadow = model.receiveShadow = true;
    model.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, .72, 0), 1.20);
    player.add(model);
    const bones = [];
    for (const entry of rig.bones) {
        const [x, y, z] = entry.offset;
        const node = new THREE.Bone();
        node.name = entry.name;
        node.position.set(x, y, -z);
        node.rotation.order = "YXZ";
        (entry.parent < 0 ? model : bones[entry.parent]).add(node);
        bones.push(node);
    }
    player.updateMatrixWorld(true);
    model.bind(new THREE.Skeleton(bones));

    const hipHeight = bones[0].position.y;
    let phase = 0;
    let moving = 0;
    let sprint = 0;
    let crouch = 0;
    let strikeTime = 0;
    let strikeClip = null;
    let strikeContact = false;
    let guarding = false, armed = false, guard = 0, strafe = 0;
    let crying = 0;
    let sob = 0;
    let time = 0;
    let leapPhase = 0;
    let leapWeight = 0;
    let leapClip = null;
    let reprimand = 0;
    let flinch = 0;
    const eyes = bones.find(bone => bone.name === "Eyes");
    const head = bones.findIndex(bone => bone.name === "Head");
    const hands = bones.filter(bone => bone.name.endsWith(" hand"));
    const upperBody = bones.map(bone => /^(Chest|Head)$| (shoulder|elbow)$/.test(bone.name));
    const chest = bones.findIndex(bone => bone.name === "Chest");
    const shoulder = bones.findIndex(bone => bone.name === "Right shoulder");
    const elbow = bones.findIndex(bone => bone.name === "Right elbow");
    let activity = null;
    let activityPhase = 0;
    let activityWeight = 0;
    const lerp = THREE.MathUtils.lerp;

    function sample(gait, cycle, index) {
        const length = gait.frames.length;
        const position = cycle * length;
        const a = Math.floor(position);
        const t = position - a;
        const previous = gait.frames[(a + length - 1) % length].pose[index];
        const start = gait.frames[a].pose[index];
        const end = gait.frames[(a + 1) % length].pose[index];
        const after = gait.frames[(a + 2) % length].pose[index];
        const m0 = (end - previous) * .5;
        const m1 = (after - start) * .5;
        return start + t * (m0 + t * (3 * (end - start) - 2 * m0 - m1 + t * (2 * (start - end) + m0 + m1)));
    }

    function sampleStrike(progress, index) {
        const keys = strikeClip.frames;
        let i = 0;
        while (i < keys.length - 2 && keys[i + 1].time < progress) i++;
        const t = THREE.MathUtils.clamp((progress - keys[i].time) / (keys[i + 1].time - keys[i].time), 0, 1);
        const a = keys[i].pose[index], b = keys[i + 1].pose[index];
        const segment = keys[i + 1].time - keys[i].time;
        const m0 = slopeAt(keys, i, index) * segment;
        const m1 = slopeAt(keys, i + 1, index) * segment;
        return a + t * (m0 + t * (3 * (b - a) - 2 * m0 - m1 + t * (2 * (a - b) + m0 + m1)));
    }

    function slopeAt(keys, i, index) {
        if (!i || i === keys.length - 1) return 0;
        const before = (keys[i].pose[index] - keys[i - 1].pose[index]) / (keys[i].time - keys[i - 1].time);
        const after = (keys[i + 1].pose[index] - keys[i].pose[index]) / (keys[i + 1].time - keys[i].time);
        return before * after <= 0 ? 0 : 2 * before * after / (before + after);
    }

    function channel(index) {
        let value = rig.idle[index];
        if (moving > .001) {
            value = lerp(value, lerp(sample(rig.walk, phase, index), sample(rig.run, phase, index), sprint), moving);
        }
        if (crouch > .001) {
            value = lerp(value, lerp(rig.crouchIdle[index], sample(rig.crouch, phase, index), moving), crouch);
        }
        if (guard > .001) value = lerp(value, lerp(rig.guardIdle[index], lerp(sample(rig.guardWalk, phase, index),
            sample(rig.guardSide, phase, index), strafe), moving), guard);
        if (activityWeight > 0) value = lerp(value, sample(activity, activityPhase, index), activityWeight);
        if (leapWeight > 0) {
            const t = leapPhase * (leapClip.frames.length - 1);
            const a = Math.min(Math.floor(t), leapClip.frames.length - 2);
            value = lerp(value, lerp(leapClip.frames[a].pose[index], leapClip.frames[a + 1].pose[index],
                smooth01(t - a)), leapWeight);
        }
        return lerp(value, rig.downPose[index], crying);
    }

    function animate(distance, dt, nextActivity = null, low = false, backwards = false, sideways = 0) {
        time += dt;
        const blend = 1 - Math.exp(-11 * dt);
        const desiredSpeed = guarding ? 1.18 : low ? rig.crouchSpeed : pace.walkSpeed;
        const amount = Math.min(1, distance / Math.max(.0001, desiredSpeed * dt));
        moving = lerp(moving, amount, blend);
        const runWeight = THREE.MathUtils.clamp((distance / Math.max(.0001, dt) - pace.walkSpeed) /
            (pace.runSpeed - pace.walkSpeed), 0, 1);
        sprint = lerp(sprint, runWeight, blend);
        crouch = lerp(crouch, low ? 1 : 0, blend);
        guard = lerp(guard, guarding && crying < .05 ? 1 : 0, blend);
        strafe = lerp(strafe, sideways, blend);
        const stride = lerp(lerp(lerp(rig.walk.stride, rig.run.stride, sprint), rig.crouch.stride, crouch),
            lerp(rig.guardWalk.stride, rig.guardSide.stride, strafe), guard);
        phase = ((phase + (backwards ? -distance : distance) / stride) % 1 + 1) % 1;
        strikeContact = false;
        if (strikeClip) {
            strikeContact = strikeTime < strikeClip.contact && strikeTime + dt >= strikeClip.contact;
            strikeTime += dt;
            if (strikeTime >= strikeClip.stride) strikeClip = null;
        }
        flinch = Math.max(0, flinch - dt / .23);
        if (nextActivity && (activity !== nextActivity || !activityWeight)) {
            activity = nextActivity;
            activityPhase = 0;
        }
        activityWeight = THREE.MathUtils.clamp(activityWeight + (nextActivity ? 1 : -1) * dt * 4, 0, 1);
        if (activityWeight > 0) activityPhase = (activityPhase + dt / activity.stride) % 1;
        const breathe = Math.sin(time * 2.3) * (1 - moving) * (1 - crying) * (1 - leapWeight);
        const recoil = Math.sin(Math.PI * flinch) ** 2 * (1 - crying);
        bones[0].position.y = hipHeight + channel(0) + breathe * .003;
        const blink = Math.abs((time + pace.walkSpeed * .71) % 3.9 - 1.8);
        if (eyes) eyes.scale.y = lerp(Math.min(1, .12 + blink * 11), .08, crying);
        const progress = strikeClip ? strikeTime / strikeClip.stride : 0;
        const attackWeight = smooth01(Math.min(progress, 1 - progress) / .18) * (1 - crying);
        const grip = Math.max(guard, attackWeight) * (1 - crying);
        for (const hand of hands) hand.scale.set(1 + .16 * grip, 1 - .26 * grip, 1 + .17 * grip);
        bones.forEach((bone, i) => {
            const start = i * 3 + 1;
            let x = channel(start);
            let y = channel(start + 1);
            let z = channel(start + 2);
            if (armed && i === shoulder) {
                x += 15 * guard;
                y -= 17 * guard;
                z += 13 * guard;
            }
            if (armed && i === elbow) x += 19 * guard;
            if (attackWeight > 0 && upperBody[i]) {
                x = lerp(x, sampleStrike(progress, start), attackWeight);
                y = lerp(y, sampleStrike(progress, start + 1), attackWeight);
                z = lerp(z, sampleStrike(progress, start + 2), attackWeight);
            }
            if (i === chest) {
                x += 3.2 * sob + breathe * 1.05 + (reprimand > 0 ? 15 : -12) * recoil;
                z += 5 * recoil;
            }
            if (i === head) {
                x += 8 * reprimand;
                z += 11 * reprimand;
            }
            bone.rotation.set(-x * radians, -y * radians, z * radians, "YXZ");
        });
    }

    function strike(withStick) {
        strikeClip = withStick ? rig.stickStrike : rig.palmStrike;
        strikeTime = 0;
        strikeContact = false;
    }

    function cry(remaining, duration = cryDuration) {
        const elapsed = duration - remaining;
        const weight = THREE.MathUtils.clamp(Math.min(elapsed / .34, remaining / .58), 0, 1);
        crying = weight * weight * (3 - 2 * weight);
        sob = Math.sin(elapsed * 27) * crying;
    }

    function leap(progress, vault) {
        leapClip = vault ? rig.vault : rig.jump;
        leapPhase = THREE.MathUtils.clamp(progress, 0, 1);
        leapWeight = THREE.MathUtils.clamp(Math.min(leapPhase / .14, (1 - leapPhase) / .17), 0, 1);
    }

    animate(0, 0);
    return {animate, bones, strike, cry, leap, cryAmount: () => crying,
        isStriking: () => Boolean(strikeClip), strikeContact: () => strikeContact,
        reactToHit: () => { flinch = 1; },
        guard: (enabled, withStick = false) => { guarding = enabled; armed = withStick; },
        caught: (value, hit = false) => {
            reprimand = value ? 1 : 0;
            if (hit) flinch = 1;
        }};
}

const residentRunMultiplier = 2.7;

function createResident(root, data, door, animator, rig) {
    const {animate, strike, cry} = animator;
    const route = data.route.map(stop => ({
        ...stop, position: new THREE.Vector3(stop.point[0], stop.point[1], -stop.point[2]),
    }));
    const child = data.door < 0;
    const walkingAcceleration = 3.5;
    const brakingAcceleration = 4;
    let stop = 0;
    let wait = route[0].dwell;
    let opening = 0;
    let speed = 0;
    let crying = 0;
    const direction = new THREE.Vector3();
    const proposed = new THREE.Vector3();
    const slide = new THREE.Vector3();
    root.visible = !route[0].hidden;
    root.position.copy(route[0].position);
    if (child) {
        direction.subVectors(route[1].position, root.position);
        root.rotation.y = -Math.atan2(direction.x, -direction.z);
    }

    function tick(dt, mayStep = null) {
        if (crying > 0) {
            crying = Math.max(0, crying - dt);
            cry(crying, residentCryDuration);
            animate(0, dt);
            return;
        }
        const current = route[stop];
        const next = (stop + 1) % route.length;
        const destination = route[next];
        const resting = wait > 0;
        const hidden = current.hidden && (resting || destination.hidden);
        root.visible = !hidden;

        if (door) {
            const open = current.door || !resting && destination.door;
            opening = THREE.MathUtils.clamp(opening + (open ? 1 : -1) * dt * 2.6, 0, 1);
            door.pivot.rotation.y = -(door.yaw + 91 * opening) * radians;
        }

        const running = !resting && destination.run;
        let traveled = 0;
        let activity = null;
        if (resting) {
            wait -= dt;
            speed = 0;
            activity = current.job ? rig[current.job] : null;
            if (activity) face(-current.yaw * radians, dt);
        } else {
            direction.subVectors(destination.position, root.position);
            const distance = direction.length();
            if (distance > .00001) {
                const desired = running ? data.speed * residentRunMultiplier : data.speed;
                const after = route[(next + 1) % route.length];
                const direct = Math.atan2(direction.x, -direction.z);
                const outgoing = Math.atan2(after.position.x - destination.position.x, destination.position.z - after.position.z);
                const difference = Math.atan2(Math.sin(outgoing - direct), Math.cos(outgoing - direct));
                const alignment = Math.cos(difference);
                const exitSpeed = destination.dwell > 0 ? 0 : desired * THREE.MathUtils.clamp((alignment + .25) / 1.21, 0, 1);
                if (Math.hypot(direction.x, direction.z) > .0001) {
                    const bend = destination.dwell <= 0 && alignment > -.7 ? difference * .80 * smooth01(1 - distance / .60) : 0;
                    face(-direct - bend, dt);
                }
                const turnFactor = .30 + .70 * THREE.MathUtils.clamp((Math.cos(-direct - root.rotation.y) + .35) / 1.25, 0, 1);
                changeSpeed(Math.min(desired, Math.sqrt(exitSpeed * exitSpeed + 2 * brakingAcceleration * distance)) * turnFactor, dt);
                const fraction = Math.min(1, speed * dt / distance);
                proposed.copy(root.position).addScaledVector(direction, fraction);
                if (mayStep && !mayStep(root.position, proposed, false)) {
                    slide.copy(root.position).addScaledVector(direction, fraction * .45);
                    slide.x += direction.z * fraction * .67;
                    slide.z -= direction.x * fraction * .67;
                    if (mayStep(root.position, slide, true)) proposed.copy(slide);
                    else proposed.copy(root.position);
                }
                traveled = Math.hypot(proposed.x - root.position.x, proposed.z - root.position.z);
                root.position.copy(proposed);
                if (root.position.distanceToSquared(destination.position) < .000000001) {
                    speed = Math.min(speed, exitSpeed);
                    stop = next;
                    wait = destination.dwell;
                }
            } else {
                stop = next;
                wait = destination.dwell;
            }
        }
        if (!hidden) animate(traveled / data.scale[1], dt, activity);
    }

    function changeSpeed(desired, dt) {
        const change = (desired < speed ? brakingAcceleration : walkingAcceleration) * dt;
        speed += THREE.MathUtils.clamp(desired - speed, -change, change);
    }

    function face(goal, dt) {
        const filtered = dampAngle(root.rotation.y, goal, 10, dt);
        root.rotation.y = turn(root.rotation.y, filtered, 300 * radians * dt);
    }

    const nextPosition = new THREE.Vector3();
    function spar(dt, player, anchor, mayApproach, mayStep, holds = false) {
        direction.subVectors(player, root.position);
        direction.y = 0;
        const distance = direction.length();
        animator.guard(child);
        if (distance > .001 && !animator.isStriking()) face(-Math.atan2(direction.x, -direction.z), dt);
        const gap = Math.max(0, distance - .78);
        const wanted = mayApproach && !animator.isStriking() && !holds
            ? Math.min(data.speed, 1.18, Math.sqrt(2 * brakingAcceleration * gap)) : 0;
        changeSpeed(wanted, dt);
        let step = mayApproach ? Math.min(dt * speed, gap) : 0;
        nextPosition.copy(root.position).addScaledVector(direction.normalize(), step);
        if (nextPosition.distanceToSquared(anchor) < 2.7 ** 2 && mayStep(resident, root.position, nextPosition, false)) {
            root.position.copy(nextPosition);
        }
        else step = 0;
        animate(step / data.scale[1], dt, holds ? rig.reprimand : null);
    }

    for (let remaining = data.offset; remaining > 0; remaining -= .1) tick(Math.min(.1, remaining));
    const resident = {tick, spar, root, data, strike, maxHealth: data.maxHealth > 0 ? data.maxHealth : 100,
        isStriking: animator.isStriking,
        strikeContact: animator.strikeContact, reactToHit: animator.reactToHit,
        faces: target => {
            const x = target.x - root.position.x, z = target.z - root.position.z;
            return -x * Math.sin(root.rotation.y) - z * Math.cos(root.rotation.y) >= .73 * Math.hypot(x, z);
        },
        canSpar: () => child && !crying && root.visible,
        canReprimand: () => !child && root.visible,
        radius: .255 * data.scale[0], height: () => (crying > 0 ? .52 : 1.50) * data.scale[1],
        isCrying: () => crying > 0, startCrying: () => { crying = residentCryDuration; }};
    return resident;
}

function createSparring(player, residents, sticks, heldStick, animator, clear, canApproach, mayStep, groundHeight) {
    const {strike, cry, caught} = animator;
    const hud = document.querySelector("#combat-hud");
    const healthBar = document.querySelector("#health");
    const tool = document.querySelector("#equipped");
    const opponentPanel = document.querySelector("#opponent");
    const opponentName = document.querySelector("#opponent-name");
    const opponentBar = document.querySelector("#opponent-health");
    const opponentVitals = document.querySelector("#opponent-vitals");
    const sobs = document.querySelector("#cry-audio");
    const swat = document.querySelector("#swat-audio");
    const reprimandBeats = [1.10, .78, .46];
    const adultAnchor = new THREE.Vector3();
    const anchor = new THREE.Vector3();
    const delta = new THREE.Vector3();
    let opponent = null;
    let restingChild = null;
    let adult = null;
    let reprimand = 0;
    let ownedStick = null;
    let nextSob = 0;
    let equipped = false;
    let health = 100;
    let foeHealth = 100;
    let aim = 0;
    let attackWithStick = false;
    let reply = 0;
    let recovery = 0;
    let rest = 0;
    let separated = 0;

    function nearbyStick() {
        if (ownedStick) return null;
        let best = 1.15 ** 2;
        let nearby = null;
        for (const stick of sticks) {
            const distance = stick.position.distanceToSquared(player.position);
            if (stick.visible && distance < best && clear(player.position, stick.position)) {
                best = distance;
                nearby = stick;
            }
        }
        return nearby;
    }

    function equip(withStick) {
        equipped = Boolean(ownedStick && withStick);
        heldStick.visible = equipped;
    }

    function pickUp() {
        const stick = nearbyStick();
        if (!stick) return false;
        stick.visible = false;
        ownedStick = stick;
        equip(true);
        return true;
    }

    function drop(yaw) {
        if (!ownedStick) return;
        delta.copy(player.position);
        delta.x += Math.sin(yaw) * .65;
        delta.z -= Math.cos(yaw) * .65;
        if (!clear(player.position, delta)) delta.copy(player.position);
        delta.y = groundHeight(delta.x, delta.z, player.position.y + .08) + .026;
        ownedStick.position.copy(delta);
        ownedStick.rotation.y = -yaw - .51;
        ownedStick.visible = true;
        ownedStick = null;
        equip(false);
    }

    function finish() {
        restingChild = opponent;
        rest = 4.5;
        opponent = null;
    }

    function attack() {
        if (animator.isStriking() || recovery > 0 || adult) return;
        aim = -player.rotation.y;
        attackWithStick = equipped;
        strike(attackWithStick);
    }

    function resolvePlayerStrike() {
        const ax = Math.sin(aim);
        const az = -Math.cos(aim);
        let best = attackWithStick ? 1.65 : 1.12;
        let target = null;
        for (const resident of residents) {
            const canSpar = resident.canSpar() && resident !== restingChild && (!opponent || resident === opponent);
            if (!resident.canReprimand() && !canSpar) continue;
            delta.subVectors(resident.root.position, player.position);
            if (Math.abs(delta.y) > .48) continue;
            const distance = Math.hypot(delta.x, delta.z);
            if (distance < .001 || distance >= best || (delta.x * ax + delta.z * az) / distance < .45 ||
                !clear(player.position, resident.root.position)) continue;
            best = distance;
            target = resident;
        }
        if (!target) return;
        if (target.canReprimand()) {
            if (opponent) finish();
            adult = target;
            adultAnchor.copy(target.root.position);
            reprimand = 1.70;
            return;
        }
        if (!opponent) {
            opponent = target;
            anchor.copy(target.root.position);
            foeHealth = target.maxHealth;
            separated = 0;
            reply = .24;
        }
        foeHealth = Math.max(0, foeHealth - (attackWithStick ? 23 : 13));
        target.reactToHit();
        if (!foeHealth) {
            opponent.startCrying();
            playCry(.66);
            nextSob = 3.42;
            finish();
        }
    }

    function tick(dt, active) {
        nextSob = Math.max(0, nextSob - dt);
        if (!nextSob && !recovery && residents.some(r => r.isCrying() && r.root.position.distanceToSquared(player.position) < 144)) {
            playCry(.52);
            nextSob = 3.42;
        }
        rest = Math.max(0, rest - dt);
        if (!rest) restingChild = null;
        if (recovery > 0) {
            recovery = Math.max(0, recovery - dt);
            cry(recovery);
            if (!recovery) health = 100;
        }
        if (!active) return;
        if (!adult && !recovery && animator.strikeContact()) resolvePlayerStrike();
        if (adult) {
            reprimandAdult(dt);
            return;
        }
        if (!opponent) return;
        const position = opponent.root.position;
        const distance = position.distanceTo(player.position);
        const visible = clear(position, player.position);
        separated = visible && distance < 5.2 ? 0 : separated + dt;
        if (separated > 2.3) {
            finish();
            return;
        }
        const advance = visible && Math.abs(position.y - player.position.y) < .48 && canApproach(position, player.position);
        opponent.spar(dt, player.position, anchor, advance, mayStep);
        reply = Math.max(0, reply - dt);
        const inReach = visible && distance <= 1.12 && opponent.faces(player.position);
        if (opponent.strikeContact() && inReach) {
            animator.reactToHit();
            hurt(11);
            if (recovery > 0) finish();
        } else if (inReach && !reply && !opponent.isStriking()) {
            opponent.strike(false);
            reply = .93;
        }
    }

    function reprimandAdult(dt) {
        const previous = reprimand;
        reprimand = Math.max(0, reprimand - dt);
        const holds = reprimand <= 1.40;
        caught(holds);
        const position = adult.root.position;
        if (holds) {
            delta.subVectors(player.position, position);
            if (Math.hypot(delta.x, delta.z) > .001) {
                player.rotation.y = turn(player.rotation.y, -Math.atan2(delta.x, -delta.z), dt * 430 * radians);
            }
        }
        const advance = clear(position, player.position) && Math.abs(position.y - player.position.y) < .48 &&
            canApproach(position, player.position);
        adult.spar(dt, player.position, adultAnchor, advance, mayStep, holds);
        reprimandBeats.forEach((beat, index) => {
            if (previous <= beat || reprimand > beat) return;
            swat.currentTime = 0;
            swat.volume = .65;
            swat.play().catch(() => {});
            caught(true, true);
            if (index === reprimandBeats.length - 1) hurt(70);
        });
        if (!reprimand || recovery > 0) {
            adult = null;
            caught(false);
        }
    }

    function hurt(damage) {
        health = Math.max(0, health - damage);
        if (!health) {
            recovery = cryDuration;
            cry(recovery);
            playCry(.88);
        }
    }

    function playCry(volume) {
        sobs.currentTime = 0;
        sobs.volume = volume;
        sobs.play().catch(() => {});
    }

    function draw(active) {
        hud.hidden = !active;
        healthBar.value = health;
        tool.textContent = equipped ? "Палка" : "Ладонь";
        opponentPanel.hidden = !opponent;
        if (opponent) {
            opponentName.textContent = `${opponent.data.name}, ${opponent.data.age} лет`;
            opponentBar.max = opponent.maxHealth;
            opponentBar.value = foeHealth;
            opponentVitals.textContent = `${foeHealth} / ${opponent.maxHealth}`;
        }
    }

    return {nearbyStick, equip, pickUp, drop, attack, tick, draw,
        canMove: () => !recovery && !adult, opponent: () => opponent,
        equipped: () => equipped, attackYaw: () => aim,
        eventMessage: () => recovery ? "Ты расплакался…" : adult ? "Взрослый поймал тебя" : "",
        busyResident: () => adult || opponent};
}

function createWalk(scene, meshes, renderer, camera) {
    const material = new THREE.MeshLambertMaterial({vertexColors: true});
    const houseMaterial = terrainAtlas("#house-surfaces", 256, true);
    const carMaterial = carPaintMaterial();
    const autoPanels = terrainAtlas("#auto-panels", 128, false);
    const glazing = new THREE.MeshPhongMaterial({vertexColors: true, color: 0xb6d4d0, shininess: 45,
        opacity: .28, transparent: true, depthWrite: false, side: THREE.DoubleSide});
    function add(name, parent = scene, x = 0, y = 0, z = 0) {
        const shading = name === "Auto panels" ? autoPanels : name.startsWith("House skin ") ? houseMaterial :
            name === "ZAZ glass" ? glazing : name.startsWith("Car ") ? carMaterial : material;
        const object = new THREE.Mesh(meshes.get(name), shading);
        object.name = name;
        object.position.set(x, y, z);
        object.receiveShadow = name !== "ZAZ glass";
        object.castShadow = !["01 Ground", "02 Roads", "ZAZ glass"].includes(name);
        parent.add(object);
        return object;
    }
    for (const name of meshes.keys()) {
        if (!/^(Gate |Door |Player |Resident |Cat |Birch |Pine )/.test(name) &&
            name !== "Watering can" && name !== "Broom" && name !== "Stick") add(name);
    }
    // Small groves keep the instanced batches eligible for camera-frustum culling.
    const forest = new Map();
    for (const tree of layout.trees) {
        const key = `${tree.zone} / ${tree.mesh}`;
        if (!forest.has(key)) forest.set(key, []);
        forest.get(key).push(tree);
    }
    const transform = new THREE.Object3D();
    for (const trees of forest.values()) {
        const batch = new THREE.InstancedMesh(meshes.get(trees[0].mesh), material, trees.length);
        trees.forEach(({placement: [x, z, size, angle]}, i) => {
            transform.position.set(x, 0, -z);
            transform.scale.setScalar(size);
            transform.rotation.y = -angle * radians;
            transform.updateMatrix();
            batch.setMatrixAt(i, transform.matrix);
        });
        batch.computeBoundingSphere();
        batch.castShadow = batch.receiveShadow = true;
        scene.add(batch);
    }

    const solids = layout.solids.map(solid => {
        const box = collisionBox(solid.box);
        box.vault = solid.vault;
        return box;
    });
    const gates = layout.gates.map(gate => {
        const pivot = new THREE.Group();
        pivot.position.set(gate.x, 0, -gate.z);
        pivot.rotation.y = -gate.yaw * radians;
        scene.add(pivot);
        add(gate.mesh, pivot);
        return {
            ...gate, pivot, angle: gate.yaw * radians, open: false,
            midpoint: new THREE.Vector3(gate.x, 0, -gate.z + Math.sign(gate.yaw) * gate.width / 2),
        };
    });

    const doors = layout.doors.map(door => {
        const pivot = new THREE.Group();
        pivot.name = door.mesh;
        const [x, y, z] = door.point;
        pivot.position.set(x, y, -z);
        pivot.rotation.y = -door.yaw * radians;
        scene.add(pivot);
        add(door.mesh, pivot);
        return {...door, pivot};
    });

    const [px, py, pz] = layout.spawn;
    const player = new THREE.Group();
    player.position.set(px, py, -pz);
    scene.add(player);
    const playerRig = rigPerson(player, meshes.get(CHILD_MESH), material, layout.rig, CHILD_MESH);
    const {animate: animateChild, bones: playerBones, cryAmount, leap: animateLeap} = playerRig;
    const heldStick = new THREE.Group();
    heldStick.name = "Stick grip";
    playerBones.find(bone => bone.name === "Right elbow").add(heldStick);
    heldStick.position.set(0, -.222, -.012);
    heldStick.rotation.set(-4 * radians, 71 * radians, -10 * radians, "YXZ");
    add("Stick", heldStick, .255, -.029, 0);
    heldStick.visible = false;
    player.rotation.y = -layout.spawnYaw * radians;

    const cat = new THREE.Group();
    scene.add(cat);
    const catBody = add("Cat body", cat);
    const tail = add("Cat tail", catBody, 0, .31, .27);
    const paws = [-.18, .14].flatMap(z => [-.083, .083].map(x => add("Cat leg", catBody, x, .201, -z)));
    const route = layout.catPath.map(({x, z}) => new THREE.Vector3(x, 0, -z));
    cat.position.copy(route[0]);
    cat.rotation.y = -Math.atan2(route[1].x - route[0].x, route[0].z - route[1].z);

    const neighborhood = new THREE.Group();
    neighborhood.name = "Residents";
    scene.add(neighborhood);
    const residents = layout.residents.map(data => {
        const root = new THREE.Group();
        root.name = data.name;
        root.scale.set(...data.scale);
        neighborhood.add(root);
        const walkSpeed = data.speed / data.scale[1];
        const pace = {walkSpeed, runSpeed: walkSpeed * residentRunMultiplier};
        const animator = rigPerson(root, meshes.get(data.mesh), material, layout.rig, data.mesh, pace);
        if (data.tool) {
            add(data.tool, animator.bones.find(bone => bone.name === "Right elbow"), 0, -.214, -.020);
        }
        return createResident(root, data, doors[data.door], animator, layout.rig);
    });

    const sticks = new THREE.Group();
    sticks.name = "Ground sticks";
    scene.add(sticks);
    const groundSticks = layout.sticks.map(({point: [x, y, z], yaw}) => {
        const branch = add("Stick", sticks, x, y, -z);
        branch.rotation.y = -yaw * radians;
        return branch;
    });
    const combatRay = new THREE.Ray();
    const combatHit = new THREE.Vector3();
    const samplePosition = new THREE.Vector3();

    function clear(from, to) {
        combatRay.origin.copy(from);
        combatRay.origin.y += .67;
        const distance = combatRay.direction.subVectors(to, from).length();
        if (distance < .001) return true;
        combatRay.direction.multiplyScalar(1 / distance);
        for (const solid of solids) {
            if (combatRay.intersectBox(solid, combatHit) && combatHit.distanceTo(combatRay.origin) < distance)
                return false;
        }
        for (let d = 0; d <= distance; d += .10) {
            combatRay.at(d, samplePosition);
            if (gates.some(gate => samplePosition.y >= .05 && samplePosition.y < 1.28 &&
                gateClearance(gate, samplePosition, gate.angle) < .11 ** 2)) return false;
        }
        return true;
    }

    function canApproach(from, to) {
        samplePosition.subVectors(to, from).setY(0).normalize().multiplyScalar(.34).add(from);
        return !solids.some(solid => solid.min.y < from.y + 1.2 && solid.max.y > from.y + .25 &&
            circleHitsBox(samplePosition.x, samplePosition.z, solid, .20)) &&
            !gates.some(gate => gateClearance(gate, samplePosition, gate.angle) < .25 ** 2);
    }

    const combat = createSparring(player, residents, groundSticks, heldStick, playerRig, clear,
        canApproach, residentMayStep, groundHeight);

    const keys = new Set();
    const direction = new THREE.Vector3();
    const target = new THREE.Vector3();
    const cameraRay = new THREE.Ray();
    const hit = new THREE.Vector3();
    const [minX, maxX, minZ, maxZ] = layout.bounds;
    let active = false;
    let yaw = layout.spawnYaw * radians;
    let pitch = 13 * radians;
    let cameraDistance = 4.8;
    let cameraHeight = py;
    let cameraCrouch = 0;
    let crouching = false;
    const velocity = new THREE.Vector3();
    const wishVelocity = new THREE.Vector3();
    let jumpRequested = false;
    let jumpTime = 0;
    let verticalSpeed = 0;
    let vault = null;
    let catStride = 0;
    let time = 0;
    let next = 1;
    let wait = layout.catStops[0];
    let routeStep = 1;
    let alarm = 0;
    let closest = null;

    function lock() {
        renderer.domElement.requestPointerLock();
    }

    document.addEventListener("pointerlockchange", () => {
        active = document.pointerLockElement === renderer.domElement;
        startCard.hidden = active;
        crosshair.hidden = !active;
        if (active) play.textContent = "Продолжить прогулку";
        else keys.clear();
    });
    document.addEventListener("pointerlockerror", () => {
        document.querySelector("#controls").textContent =
            "Браузер заблокировал захват мыши. Открой файл в отдельной вкладке Chrome или Firefox.";
    });
    play.addEventListener("click", lock);
    renderer.domElement.addEventListener("click", () => {
        if (active) combat.attack();
        else lock();
    });
    window.addEventListener("blur", () => keys.clear());
    document.addEventListener("mousemove", event => {
        if (!active) return;
        yaw += event.movementX * .00275;
        pitch = THREE.MathUtils.clamp(pitch - event.movementY * .00275, -.27, 1.01);
    });
    document.addEventListener("keydown", event => {
        if (!active) return;
        event.preventDefault();
        keys.add(event.code);
        if (event.repeat || !combat.canMove()) return;
        if (event.code === "KeyC" && !combat.opponent() && !vault && !jumpTime) {
            const blocked = crouching && solids.some(solid => solid.min.y >= player.position.y + 1.16 &&
                solid.min.y <= player.position.y + 1.62 && circleHitsBox(player.position.x, player.position.z, solid, .24));
            if (!blocked) crouching = !crouching;
        }
        if (event.code === "Space") jumpRequested = true;
        if (event.code === "KeyF") combat.attack();
        if (event.code === "KeyG") combat.drop(yaw);
        if (event.code === "Digit1" || event.code === "Digit2") combat.equip(event.code === "Digit2");
        if (event.code === "KeyE" && !combat.pickUp() && closest) {
            const closed = closest.yaw * radians;
            if (!closest.open || gateClearance(closest, player.position, closed) >= .36 ** 2) {
                closest.open = !closest.open;
            }
        }
    });
    document.addEventListener("keyup", event => keys.delete(event.code));

    function approachesPerson(from, to, height, other, otherHeight, radius) {
        if (to.y >= other.y + otherHeight || to.y + height <= other.y) return false;
        const distance = (to.x - other.x) ** 2 + (to.z - other.z) ** 2;
        return distance < radius ** 2 && distance < (from.x - other.x) ** 2 + (from.z - other.z) ** 2;
    }

    function residentMayStep(resident, from, to, lateral) {
        const heroHeight = cryAmount() > .65 ? .48 : crouching ? 1.20 : 1.62;
        if (approachesPerson(from, to, resident.height(), player.position, heroHeight, resident.radius + .25)) return false;
        if (residents.some(other => other !== resident && other.root.visible &&
            approachesPerson(from, to, resident.height(), other.root.position, other.height(), resident.radius + other.radius))) {
            return false;
        }
        return !lateral || !solids.some(solid => solid.min.y < to.y + .8 &&
            solid.max.y > to.y + .30 && circleHitsBox(to.x, to.z, solid, resident.radius)) &&
            !gates.some(gate => gateClearance(gate, to, gate.angle) < (resident.radius + .07) ** 2);
    }

    function groundHeight(x, z, ceiling) {
        let floor = 0;
        for (const solid of solids) {
            if (solid.max.y <= ceiling && solid.max.y > floor && circleHitsBox(x, z, solid, .236)) {
                floor = solid.max.y;
            }
        }
        return floor;
    }

    const moveCandidate = new THREE.Vector3();

    function moveAxis(dx, dz, airborne) {
        if (dx === 0 && dz === 0) return;
        const position = player.position;
        const x = THREE.MathUtils.clamp(position.x + dx, minX + .25, maxX - .25);
        const z = THREE.MathUtils.clamp(position.z + dz, -maxZ + .25, -minZ - .25);
        const height = crouching ? 1.20 : 1.62;
        const stepLimit = airborne ? .025 : .32;
        for (const solid of solids) {
            if (solid.min.y < position.y + height && solid.max.y > position.y + stepLimit &&
                circleHitsBox(x, z, solid, .242)) return;
        }
        moveCandidate.set(x, airborne ? position.y : groundHeight(x, z, position.y + stepLimit), z);
        if (moveCandidate.y < 1.275 && gates.some(gate => gateClearance(gate, moveCandidate, gate.angle) < .316 ** 2)) return;
        if (residents.some(person => person.root.visible && approachesPerson(position, moveCandidate,
            height, person.root.position, person.height(), .25 + person.radius))) return;
        position.copy(moveCandidate);
    }

    const vaultRay = new THREE.Ray();
    const vaultHit = new THREE.Vector3();
    const vaultCheck = new THREE.Vector3();

    function vaultPoint(plan, phase, result) {
        result.lerpVectors(plan.from, plan.to, smooth01((phase - .22) / .55));
        const lift = Math.min(smooth01(phase / .32), smooth01((1 - phase) / .32));
        result.y = THREE.MathUtils.lerp(result.y, plan.peak, lift);
        return result;
    }

    function freeAt(point) {
        if (point.x < minX + .25 || point.x > maxX - .25 || point.z < -maxZ + .25 || point.z > -minZ - .25) return false;
        return !solids.some(solid => solid.max.y > point.y + .026 && solid.min.y < point.y + 1.62 &&
            circleHitsBox(point.x, point.z, solid, .232)) &&
            !gates.some(gate => point.y < 1.26 && gateClearance(gate, point, gate.angle) < .306 ** 2) &&
            !residents.some(person => person.root.visible && point.y < person.root.position.y + person.height() &&
                point.y + 1.62 > person.root.position.y &&
                (point.x - person.root.position.x) ** 2 + (point.z - person.root.position.z) ** 2 < (.23 + person.radius) ** 2);
    }

    function tryVault(heading) {
        vaultRay.origin.copy(player.position);
        vaultRay.origin.y += .70;
        vaultRay.direction.copy(heading);
        let nearest = 1.08;
        let fence = null;
        const gateBounds = new THREE.Box3();
        function consider(box, canVault) {
            if (!vaultRay.intersectBox(box, vaultHit)) return;
            const distance = vaultHit.distanceTo(vaultRay.origin);
            if (distance >= nearest) return;
            nearest = distance;
            const normal = box.max.x - box.min.x > box.max.z - box.min.z ? Math.abs(heading.z) : Math.abs(heading.x);
            fence = canVault && normal >= .62 ? box : null;
        }
        for (const box of solids) consider(box, box.vault);
        for (const gate of gates) {
            const a = gate.pivot.position;
            const bx = a.x + gate.width * Math.cos(gate.angle);
            const bz = a.z + gate.width * Math.sin(gate.angle);
            gateBounds.min.set(Math.min(a.x, bx)-.08, 0, Math.min(a.z, bz)-.08);
            gateBounds.max.set(Math.max(a.x, bx)+.08, 1.28, Math.max(a.z, bz)+.08);
            consider(gateBounds.clone(), true);
        }
        if (!fence) return false;
        const from = player.position.clone();
        const to = from.clone().addScaledVector(heading, nearest + .88);
        to.y = groundHeight(to.x, to.z, from.y + .54);
        const plan = {from, to, peak: fence.max.y + .23, elapsed: 0};
        for (let i = 1; i <= 18; i++) {
            if (!freeAt(vaultPoint(plan, i / 18, vaultCheck))) return false;
        }
        vault = plan;
        velocity.set(0, 0, 0);
        player.rotation.y = -Math.atan2(heading.x, -heading.z);
        return true;
    }

    function stepAir(dt) {
        jumpTime += dt;
        verticalSpeed -= 18 * dt;
        const position = player.position;
        const y = position.y + verticalSpeed * dt;
        if (verticalSpeed <= 0) {
            const floor = groundHeight(position.x, position.z, position.y + .026);
            if (y <= floor) {
                position.y = floor;
                verticalSpeed = jumpTime = 0;
                return;
            }
        }
        if (verticalSpeed > 0 && solids.some(solid => solid.min.y > position.y + 1.6 &&
            solid.min.y <= y + 1.62 && circleHitsBox(position.x, position.z, solid, .24))) {
            verticalSpeed = 0;
            return;
        }
        position.y = y;
    }

    function walk(dt) {
        const foe = combat.opponent();
        const held = (a, b) => Number(keys.has(a) || keys.has(b));
        const forward = held("KeyW", "ArrowUp") - held("KeyS", "ArrowDown");
        const side = held("KeyD", "ArrowRight") - held("KeyA", "ArrowLeft");
        const running = forward >= 0 && !crouching && (keys.has("ShiftLeft") || keys.has("ShiftRight"));
        const canMove = active && combat.canMove();
        const walking = canMove && (side || forward);
        playerRig.guard(Boolean(foe) && canMove, combat.equipped());
        const oldX = player.position.x;
        const oldZ = player.position.z;
        if (walking) {
            direction.set(Math.sin(yaw) * forward + Math.cos(yaw) * side, 0,
                -Math.cos(yaw) * forward + Math.sin(yaw) * side).normalize();
        }
        if (jumpRequested && canMove && !jumpTime && !vault && !crouching) {
            if (!walking) direction.set(Math.sin(yaw), 0, -Math.cos(yaw));
            if (!tryVault(direction)) {
                jumpTime = .001;
                verticalSpeed = 4.9;
            }
        }
        jumpRequested = false;
        if (vault) {
            vault.elapsed += dt;
            const phase = Math.min(1, vault.elapsed / .90);
            if (!freeAt(vaultPoint(vault, phase, vaultCheck))) {
                vault = null;
                jumpTime = .38;
                verticalSpeed = -1.3;
            } else {
                player.position.copy(vaultCheck);
                if (phase >= 1) vault = null;
            }
            animateLeap(vault ? phase : 0, true);
            animateChild(0, dt);
            return;
        }

        const desiredSpeed = foe ? 1.18
            : crouching ? layout.rig.crouchSpeed : running ? layout.rig.runSpeed : layout.rig.walkSpeed;
        wishVelocity.copy(direction).multiplyScalar(walking ? desiredSpeed : 0);
        if (canMove) velocity.lerp(wishVelocity, 1 - Math.exp(-(walking ? 14 : 19) * dt));
        else velocity.set(0, 0, 0);
        if (!walking && velocity.lengthSq() < .0004) velocity.set(0, 0, 0);
        moveAxis(velocity.x * dt, 0, Boolean(jumpTime));
        moveAxis(0, velocity.z * dt, Boolean(jumpTime));

        const striking = playerRig.isStriking();
        if (canMove && (walking || striking || foe)) {
            let facing = forward < 0 ? -yaw : -Math.atan2(direction.x, -direction.z);
            if (foe) facing = -Math.atan2(foe.root.position.x - player.position.x, player.position.z - foe.root.position.z);
            if (striking) facing = -combat.attackYaw();
            player.rotation.y = dampAngle(player.rotation.y, facing, striking ? 26 : 13, dt);
        }
        if (jumpTime) stepAir(dt);
        animateLeap(jumpTime ? Math.min(.94, jumpTime / .56) : 0, false);
        const dx = player.position.x - oldX;
        const dz = player.position.z - oldZ;
        const traveled = Math.hypot(dx, dz);
        const angle = player.rotation.y;
        const lateral = (dx * Math.cos(angle) - dz * Math.sin(angle)) / Math.max(.0001, traveled);
        const fore = (-dx * Math.sin(angle) - dz * Math.cos(angle)) / Math.max(.0001, traveled);
        const sideways = foe ? THREE.MathUtils.clamp((Math.abs(lateral) - .38) / .44, 0, 1) : 0;
        const backwards = foe || striking ? (sideways > .5 ? lateral < 0 : fore < 0) :
            (forward < 0 ? dx * Math.sin(yaw) - dz * Math.cos(yaw) < 0 : !walking && fore < 0);
        animateChild(jumpTime ? 0 : traveled, dt, null, crouching && !foe, backwards, sideways);
    }

    function manageGates(dt) {
        closest = null;
        let distance = 1.72 ** 2;
        for (const gate of gates) {
            const toward = gate.yaw * radians + (gate.open ? -98 * radians : 0);
            const angle = turn(gate.angle, toward, dt * 3.75);
            const clearance = gateClearance(gate, player.position, angle);
            if (clearance >= .36 ** 2 || clearance >= gateClearance(gate, player.position, gate.angle)) {
                gate.angle = angle;
            }
            gate.pivot.rotation.y = -gate.angle;
            const near = (player.position.x - gate.midpoint.x) ** 2 + (player.position.z - gate.midpoint.z) ** 2;
            if (near < distance) {
                distance = near;
                closest = gate;
            }
        }
        const message = combat.eventMessage();
        const stick = active && !message && combat.nearbyStick();
        hint.hidden = !active || (!message && !stick && !closest);
        hint.firstElementChild.hidden = Boolean(message);
        if (!hint.hidden) {
            hint.lastElementChild.textContent = message || (stick ? "Подобрать палку" :
                closest.open ? "Закрыть калитку" : "Открыть калитку");
        }
    }

    function paceCat(dt) {
        const away = direction.subVectors(cat.position, player.position);
        away.y = 0;
        const wrap = i => (i + route.length) % route.length;
        alarm = Math.max(0, alarm - dt);
        if (away.lengthSq() < layout.catAlertRadius ** 2) {
            let previous = wrap(next - routeStep);
            if (cat.position.distanceToSquared(route[previous]) < .0144) previous = wrap(previous - routeStep);
            const forward = target.subVectors(route[next], cat.position).normalize().dot(away);
            const backward = target.subVectors(route[previous], cat.position).normalize().dot(away);
            if (backward > forward + .08) {
                routeStep = -routeStep;
                next = previous;
            }
            alarm = 1.3;
            wait = 0;
        }
        const fleeing = alarm > 0;
        let amount = 0;
        if (wait > 0) {
            wait -= dt;
        } else {
            const goal = route[next];
            direction.subVectors(goal, cat.position);
            const distance = direction.length();
            if (distance < .05) {
                wait = fleeing ? 0 : layout.catStops[next];
                next = wrap(next + routeStep);
            } else {
                amount = Math.min(distance, (fleeing ? layout.catFleeSpeed : 1.07) * dt);
                cat.position.addScaledVector(direction, amount / distance);
                cat.rotation.y = turn(cat.rotation.y, -Math.atan2(direction.x, -direction.z), dt * (fleeing ? 16.6 : 6.1));
            }
        }
        catStride += amount * (fleeing ? 10 : 16);
        const swing = amount > 0 ? Math.sin(catStride) * (fleeing ? .84 : .54) : 0;
        paws.forEach((paw, i) => {
            const sign = fleeing ? (i < 2 ? 1 : -1) : (i === 0 || i === 3 ? 1 : -1);
            paw.rotation.x = THREE.MathUtils.lerp(paw.rotation.x, sign * swing, Math.min(1, dt * 15));
        });
        catBody.position.y = amount > 0 ? (fleeing ? .055 : .018) * Math.abs(Math.cos(catStride)) : 0;
        tail.rotation.y = Math.sin(time * 2.7) * .33;
        tail.rotation.z = Math.sin(time * 1.8) * .16;
    }

    function orbitCamera(dt) {
        cameraHeight = THREE.MathUtils.lerp(cameraHeight, player.position.y, 1 - Math.exp(-13 * dt));
        cameraCrouch = THREE.MathUtils.lerp(cameraCrouch, crouching ? .25 : 0, 1 - Math.exp(-13 * dt));
        target.set(player.position.x, cameraHeight + 1.26 - cameraCrouch - .60 * cryAmount(), player.position.z);
        direction.set(-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch));
        cameraRay.set(target, direction);
        let wanted = 4.8;
        for (const solid of solids) {
            if (cameraRay.intersectBox(solid, hit)) {
                wanted = Math.min(wanted, Math.max(.36, hit.distanceTo(target) - .20));
            }
        }
        cameraDistance = Math.min(wanted, cameraDistance + dt * 5.5);
        camera.position.copy(target).addScaledVector(direction, cameraDistance);
        camera.lookAt(target);
    }

    return (dt) => {
        time += dt;
        walk(dt);
        manageGates(dt);
        paceCat(dt);
        combat.tick(dt, active);
        for (const resident of residents) {
            if (resident !== combat.busyResident()) {
                resident.tick(dt, (from, to, lateral) => residentMayStep(resident, from, to, lateral));
            }
        }
        combat.draw(active);
        orbitCamera(dt);
    };
}

function dampAngle(current, goal, rate, dt) {
    const delta = Math.atan2(Math.sin(goal - current), Math.cos(goal - current));
    return current + delta * (1 - Math.exp(-rate * dt));
}

function turn(current, goal, maxStep) {
    const delta = Math.atan2(Math.sin(goal - current), Math.cos(goal - current));
    return current + THREE.MathUtils.clamp(delta, -maxStep, maxStep);
}

async function main() {
    const meshes = await loadMeshes();
    const renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: "high-performance"});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0xbecab6);
    document.body.prepend(renderer.domElement);
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0xbecab6, .018);
    const sky = createSky(scene);
    const camera = new THREE.PerspectiveCamera(57, 1, .16, 118);
    scene.add(new THREE.HemisphereLight(0xffefd9, 0x7c8166, 2.02));
    const sun = new THREE.DirectionalLight(0xffd8a3, 2.05);
    sun.castShadow = true;
    sun.shadow.camera.left = -43;
    sun.shadow.camera.right = 43;
    sun.shadow.camera.top = 40;
    sun.shadow.camera.bottom = -38;
    sun.shadow.camera.far = 106;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -.00032;
    sun.shadow.normalBias = .13;
    scene.add(sun, sun.target);

    const tick = createWalk(scene, meshes, renderer, camera);
    const resize = () => {
        renderer.setSize(window.innerWidth, window.innerHeight);
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", resize);
    resize();
    play.disabled = false;

    let previous = performance.now();
    renderer.setAnimationLoop(now => {
        const dt = Math.max(0, Math.min(.12, (now - previous) / 1000));
        previous = now;
        const steps = Math.ceil(dt * 60);
        for (let i = 0; i < steps; i++) tick(dt / steps);
        sky.position.copy(camera.position);
        const shadowX = Math.round(camera.position.x * 24) / 24;
        const shadowZ = Math.round(camera.position.z * 24) / 24;
        sun.target.position.set(shadowX, 0, shadowZ);
        sun.position.set(shadowX - 36, 32, shadowZ + 42);
        renderer.render(scene, camera);
    });
}

main().catch(error => {
    console.error(error);
    document.querySelector("#controls").textContent =
        "Не получилось запустить 3D-сцену. Открой этот файл в свежей версии Chrome или Firefox с WebGL.";
});
