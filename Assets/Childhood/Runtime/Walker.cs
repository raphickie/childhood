using System.Collections.Generic;
using UnityEngine;

namespace Childhood
{
    internal sealed class Walker
    {
        public const int ResidentLayer = 8;
        public const int WorldMask = ~((1 << 2) | (1 << ResidentLayer));
        private const int OccupancyMask = ~(1 << 2);
        private const float StandingHeight = 1.62f;
        private const float CrouchingHeight = 1.20f;
        private const float VaultDuration = .90f;
        private const float JumpDuration = .56f;

        private readonly CharacterController controller;
        private readonly Transform body;
        private readonly ChildLocomotion locomotion;
        private readonly Camera camera;
        private readonly HashSet<Collider> vaultFences;
        private float yaw, pitch = 13f, verticalSpeed, cameraHeight, cameraCrouch, cameraDistance = 4.8f;
        private float jumpTime, vaultTime = -1f, vaultPeak;
        private Vector3 vaultStart, vaultEnd, velocity, strikeAim;

        public Vector3 Position => controller.transform.position;
        public bool IsStriking => locomotion.IsStriking;
        public bool StrikeContact => locomotion.StrikeContact;
        public Vector3 StrikeAim => strikeAim;
        public Vector3 Aim => Quaternion.Euler(0f, yaw, 0f) * Vector3.forward;
        public float Height => locomotion.CryAmount > .65f ? .48f : controller.height;
        public bool Crouching { get; private set; }

        public Walker(CharacterController controller, Transform body, ChildLocomotion locomotion,
            Camera camera, float yaw, HashSet<Collider> vaultFences)
        {
            this.controller = controller;
            this.body = body;
            this.locomotion = locomotion;
            this.camera = camera;
            this.yaw = yaw;
            this.vaultFences = vaultFences;
            body.rotation = Quaternion.Euler(0f, yaw, 0f);
            TickCamera(0f);
        }

        public void Strike(bool withStick)
        {
            strikeAim = body.forward;
            locomotion.Strike(withStick);
        }

        public void ReactToHit() => locomotion.ReactToHit();

        public void Cry(float remaining) => locomotion.SetCry(remaining);

        public void Reprimand(bool caught, bool hit = false) => locomotion.SetReprimand(caught, hit);

        public void TurnAway(Vector3 from, float dt)
        {
            Vector3 direction = Position - from;
            direction.y = 0f;
            if (direction.sqrMagnitude > .001f)
                body.rotation = Quaternion.RotateTowards(body.rotation, Quaternion.LookRotation(direction), 430f * dt);
        }

        private void ToggleCrouch()
        {
            float r = controller.radius;
            if (Crouching && Physics.CheckCapsule(Position + Vector3.up * (CrouchingHeight - r),
                    Position + Vector3.up * (StandingHeight - r), r - .02f, OccupancyMask, QueryTriggerInteraction.Ignore))
                return;
            Crouching = !Crouching;
            float height = Crouching ? CrouchingHeight : StandingHeight;
            controller.height = height;
            controller.center = Vector3.up * (height / 2f);
        }

        public void Tick(bool active, VillageResident opponent, bool armed)
        {
            float dt = Time.deltaTime;
            bool guarding = opponent != null;
            locomotion.Guard(guarding && active, armed);
            Vector2 input = Vector2.zero;
            bool running = false;
            if (active)
            {
                yaw += Input.GetAxisRaw("Mouse X") * 3.1f;
                pitch = Mathf.Clamp(pitch - Input.GetAxisRaw("Mouse Y") * 3.1f, -16f, 58f);
                float horizontal = Held(KeyCode.D, KeyCode.RightArrow) - Held(KeyCode.A, KeyCode.LeftArrow);
                float longitudinal = Held(KeyCode.W, KeyCode.UpArrow) - Held(KeyCode.S, KeyCode.DownArrow);
                input = Vector2.ClampMagnitude(new Vector2(horizontal, longitudinal), 1f);
                if (!guarding && vaultTime < 0f && jumpTime <= 0f && Input.GetKeyDown(KeyCode.C))
                    ToggleCrouch();
                running = input.y >= 0f && !Crouching && (Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift));
            }

            Vector3 target = Quaternion.Euler(0f, yaw, 0f) * new Vector3(input.x, 0f, input.y);
            if (active && !Crouching && vaultTime < 0f && jumpTime <= 0f && Input.GetKeyDown(KeyCode.Space) && controller.isGrounded)
            {
                Vector3 direction = target.sqrMagnitude > .01f ? target.normalized : Aim;
                if (!TryVault(direction))
                {
                    verticalSpeed = 4.9f;
                    jumpTime = .001f;
                }
            }
            if (vaultTime >= 0f)
            {
                TickVault(dt);
                return;
            }

            bool hasInput = target.sqrMagnitude > .01f;
            if (active && (IsStriking || guarding || hasInput))
            {
                Vector3 facing = IsStriking ? strikeAim : guarding ? opponent.Position - Position : input.y < 0f ? Aim : target;
                facing.y = 0f;
                if (facing.sqrMagnitude > .0001f)
                {
                    Quaternion goal = Quaternion.LookRotation(facing);
                    float delta = Quaternion.Angle(body.rotation, goal);
                    float step = IsStriking ? 1f - Mathf.Exp(-26f * dt) : 1f - Mathf.Exp(-13f * dt);
                    body.rotation = Quaternion.RotateTowards(body.rotation, goal, delta * step);
                }
            }

            if (jumpTime > 0f)
                jumpTime += dt;
            else if (controller.isGrounded)
                verticalSpeed = -3f;
            verticalSpeed = Mathf.Max(-12f, verticalSpeed - 18f * dt);

            Vector3 previous = Position;
            float desiredSpeed = guarding ? 1.18f : locomotion.Speed(running, Crouching);
            velocity = active ? Vector3.Lerp(velocity, target * desiredSpeed, 1f - Mathf.Exp(-(hasInput ? 14f : 19f) * dt)) : Vector3.zero;
            if (!hasInput && velocity.sqrMagnitude < .0004f)
                velocity = Vector3.zero;
            controller.stepOffset = jumpTime > 0f ? 0f : .32f;
            CollisionFlags contact = controller.Move((velocity + Vector3.up * verticalSpeed) * dt);
            if ((contact & CollisionFlags.Above) != 0)
                verticalSpeed = Mathf.Min(0f, verticalSpeed);
            if ((contact & CollisionFlags.Below) != 0 && verticalSpeed <= 0f)
            {
                verticalSpeed = -3f;
                jumpTime = 0f;
            }
            Vector3 traveled = Position - previous;
            traveled.y = 0f;
            locomotion.SetLeap(jumpTime > 0f ? Mathf.Min(.94f, jumpTime / JumpDuration) : 0f, false);
            Vector3 motion = traveled.normalized;
            float lateral = Vector3.Dot(body.right, motion);
            float fore = Vector3.Dot(body.forward, motion);
            float sideways = guarding ? Mathf.InverseLerp(.38f, .82f, Mathf.Abs(lateral)) : 0f;
            bool backwards = guarding || IsStriking ? (sideways > .5f ? lateral < 0f : fore < 0f) : (input.y < 0f ? Vector3.Dot(Aim, motion) < 0f : !hasInput && fore < 0f);
            locomotion.Tick(jumpTime > 0f ? 0f : traveled.magnitude, dt, low: Crouching && !guarding,
                backwards: backwards, sideways: sideways);
        }

        private bool TryVault(Vector3 direction)
        {
            if (!Physics.Raycast(Position + Vector3.up * .70f, direction, out RaycastHit fence, 1.08f,
                    WorldMask, QueryTriggerInteraction.Ignore) || !vaultFences.Contains(fence.collider)
                || Vector3.Dot(-fence.normal, direction) < .62f)
                return false;

            Vector3 end = Position + direction * (fence.distance + .88f);
            if (!Physics.Raycast(end + Vector3.up * .54f, Vector3.down, out RaycastHit floor, 1.14f,
                    WorldMask, QueryTriggerInteraction.Ignore))
                return false;
            end.y = floor.point.y;
            Vector3 start = Position;
            float peak = fence.collider.bounds.max.y + .23f;
            for (int i = 1; i <= 18; i++)
                if (!FreeAt(VaultPoint(start, end, peak, i / 18f)))
                    return false;

            vaultStart = start;
            vaultEnd = end;
            vaultPeak = peak;
            vaultTime = 0f;
            body.rotation = Quaternion.LookRotation(direction);
            velocity = Vector3.zero;
            controller.stepOffset = 0f;
            return true;
        }

        private bool FreeAt(Vector3 point)
        {
            const float radius = .23f;
            return !Physics.CheckCapsule(point + Vector3.up * (radius + .035f),
                point + Vector3.up * (StandingHeight - radius), radius, OccupancyMask, QueryTriggerInteraction.Ignore);
        }

        private static Vector3 VaultPoint(Vector3 start, Vector3 end, float peak, float t)
        {
            float travel = Mathf.SmoothStep(0f, 1f, (t - .22f) / .55f);
            Vector3 point = Vector3.Lerp(start, end, travel);
            float rise = Mathf.SmoothStep(0f, 1f, t / .32f);
            float fall = Mathf.SmoothStep(0f, 1f, (1f - t) / .32f);
            point.y = Mathf.Lerp(point.y, peak, Mathf.Min(rise, fall));
            return point;
        }

        private void TickVault(float dt)
        {
            vaultTime = Mathf.Min(VaultDuration, vaultTime + dt);
            float phase = vaultTime / VaultDuration;
            Vector3 next = VaultPoint(vaultStart, vaultEnd, vaultPeak, phase);
            controller.Move(next - Position);
            if (phase >= 1f || (Position - next).sqrMagnitude > .10f)
            {
                vaultTime = -1f;
                verticalSpeed = 0f;
            }
            locomotion.SetLeap(vaultTime >= 0f ? phase : 0f, true);
            locomotion.Tick(0f, dt);
        }

        public void TickCamera(float deltaTime)
        {
            Quaternion orbit = Quaternion.Euler(pitch, yaw, 0f);
            Vector3 target = Position;
            cameraHeight = Mathf.Lerp(cameraHeight, target.y, 1f - Mathf.Exp(-13f * deltaTime));
            cameraCrouch = Mathf.Lerp(cameraCrouch, Crouching ? .25f : 0f, 1f - Mathf.Exp(-13f * deltaTime));
            target.y = cameraHeight + 1.26f - cameraCrouch - .60f * locomotion.CryAmount;
            Vector3 direction = orbit * Vector3.back;
            const float wanted = 4.8f;
            if (Physics.SphereCast(target, .17f, direction, out RaycastHit hit, wanted, WorldMask,
                    QueryTriggerInteraction.Ignore))
                cameraDistance = Mathf.Min(cameraDistance, Mathf.Max(.36f, hit.distance - .09f));
            else
                cameraDistance = Mathf.MoveTowards(cameraDistance, wanted, deltaTime * 5.5f);
            camera.transform.SetPositionAndRotation(target + direction * cameraDistance, orbit);
        }

        private static float Held(KeyCode first, KeyCode second) => Input.GetKey(first) || Input.GetKey(second) ? 1f : 0f;
    }
}
