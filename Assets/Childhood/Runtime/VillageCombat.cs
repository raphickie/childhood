using UnityEngine;

namespace Childhood
{
    internal sealed class VillageCombat
    {
        private readonly Walker walker;
        private readonly VillageResident[] residents;
        private readonly Transform[] sticks;
        private readonly Transform heldStick;
        private readonly AudioSource audio;
        private readonly AudioClip sobs, swat;
        private VillageResident opponent, restingChild, adult;
        private Vector3 adultAnchor;
        private float reprimand;
        private Vector3 anchor;
        private float reply, recovery, rest, separated;
        private bool attackWithStick;
        private Transform ownedStick;
        private float nextSob;

        public int Health { get; private set; } = 100;
        public int OpponentHealth { get; private set; } = 100;
        public VillageResident Opponent => opponent;
        public bool Equipped { get; private set; }
        public bool IsCrying => recovery > 0f;
        public bool IsReprimanding => adult != null;
        public bool CanMove => !IsCrying && !IsReprimanding;
        public VillageResident BusyResident => adult ?? opponent;
        private const float ReprimandDuration = 1.70f;
        // Time remaining at the three contacts in the adult's animation.
        private static readonly float[] ReprimandBeats = { 1.10f, .78f, .46f };

        public VillageCombat(Walker walker, VillageResident[] residents, Transform[] sticks, Transform heldStick, AudioSource audio)
        {
            this.walker = walker;
            this.residents = residents;
            this.sticks = sticks;
            this.heldStick = heldStick;
            this.audio = audio;
            sobs = Resources.Load<AudioClip>("Crying");
            swat = Resources.Load<AudioClip>("Swat");
        }

        public Transform NearbyStick()
        {
            if (ownedStick != null)
                return null;
            Transform closest = null;
            float best = 1.15f * 1.15f;
            foreach (Transform stick in sticks)
            {
                float distance = (stick.position - walker.Position).sqrMagnitude;
                if (!stick.gameObject.activeSelf || distance >= best || !Clear(walker.Position, stick.position))
                    continue;
                closest = stick;
                best = distance;
            }
            return closest;
        }

        public bool PickUp()
        {
            Transform stick = NearbyStick();
            if (stick == null)
                return false;
            stick.gameObject.SetActive(false);
            ownedStick = stick;
            Equip(true);
            return true;
        }

        public void Equip(bool stick)
        {
            Equipped = ownedStick != null && stick;
            heldStick.gameObject.SetActive(Equipped);
        }

        public void Drop()
        {
            if (ownedStick == null)
                return;

            Vector3 point = walker.Position + walker.Aim * .65f;
            if (!Clear(walker.Position, point))
                point = walker.Position;
            if (!Physics.Raycast(point + Vector3.up * .35f, Vector3.down, out RaycastHit floor,
                    4f, Walker.WorldMask, QueryTriggerInteraction.Ignore))
                return;

            ownedStick.position = floor.point + Vector3.up * .025f;
            ownedStick.rotation = Quaternion.LookRotation(walker.Aim) * Quaternion.Euler(0f, 29f, 0f);
            ownedStick.gameObject.SetActive(true);
            ownedStick = null;
            Equip(false);
        }

        public void Attack()
        {
            if (walker.IsStriking || !CanMove)
                return;
            attackWithStick = Equipped;
            walker.Strike(attackWithStick);
        }

        private void ResolvePlayerStrike()
        {
            VillageResident target = null;
            float range = attackWithStick ? 1.65f : 1.12f;
            foreach (VillageResident resident in residents)
            {
                bool sparringTarget = resident.CanSpar && resident != restingChild && (opponent == null || resident == opponent);
                if (!resident.CanReprimand && !sparringTarget)
                    continue;
                Vector3 delta = resident.Position - walker.Position;
                if (Mathf.Abs(delta.y) > .48f)
                    continue;
                delta.y = 0f;
                float distance = delta.magnitude;
                if (distance >= range || Vector3.Dot(delta.normalized, walker.StrikeAim) < .45f || !Clear(walker.Position, resident.Position))
                    continue;
                range = distance;
                target = resident;
            }
            if (target == null)
                return;
            if (target.CanReprimand)
            {
                if (opponent != null)
                    Finish();
                adult = target;
                adultAnchor = target.Position;
                reprimand = ReprimandDuration;
                return;
            }

            if (opponent == null)
            {
                opponent = target;
                anchor = target.Position;
                OpponentHealth = target.MaxHealth;
                separated = 0f;
                reply = .24f;
            }

            OpponentHealth = Mathf.Max(0, OpponentHealth - (attackWithStick ? 23 : 13));
            target.ReactToHit();
            if (OpponentHealth == 0)
            {
                opponent.StartCrying();
                PlayCry(.66f);
                nextSob = 3.42f;
                Finish();
            }
        }

        public void Tick(float dt, bool active)
        {
            nextSob = Mathf.Max(0f, nextSob - dt);
            if (nextSob == 0f && !IsCrying)
            {
                foreach (VillageResident resident in residents)
                {
                    if (!resident.IsCrying || (resident.Position - walker.Position).sqrMagnitude > 12f * 12f)
                        continue;
                    PlayCry(.52f);
                    nextSob = 3.42f;
                    break;
                }
            }
            rest = Mathf.Max(0f, rest - dt);
            if (rest == 0f)
                restingChild = null;

            if (recovery > 0f)
            {
                recovery = Mathf.Max(0f, recovery - dt);
                walker.Cry(recovery);
                if (recovery == 0f)
                    Health = 100;
            }
            if (!active)
                return;
            if (CanMove && walker.StrikeContact)
                ResolvePlayerStrike();
            if (adult != null)
            {
                TickReprimand(dt);
                return;
            }
            if (opponent == null)
                return;

            float distance = Vector3.Distance(walker.Position, opponent.Position);
            bool clear = Clear(opponent.Position, walker.Position);
            separated = clear && distance < 5.2f ? 0f : separated + dt;
            if (separated > 2.3f)
            {
                Finish();
                return;
            }

            opponent.TickSpar(dt, walker.Position, anchor, clear && CanApproach(opponent.Position, walker.Position));
            reply = Mathf.Max(0f, reply - dt);
            bool inReach = clear && distance <= 1.12f && opponent.Faces(walker.Position);
            if (opponent.StrikeContact && inReach)
            {
                walker.ReactToHit();
                Hurt(11);
                if (IsCrying)
                    Finish();
            }
            else if (inReach && reply == 0f && !opponent.IsStriking)
            {
                opponent.Strike();
                reply = .93f;
            }
        }

        private void TickReprimand(float dt)
        {
            float previous = reprimand;
            reprimand = Mathf.Max(0f, reprimand - dt);
            bool holds = reprimand <= 1.40f;
            if (holds)
                walker.TurnAway(adult.Position, dt);
            walker.Reprimand(holds);
            Vector3 position = adult.Position;
            adult.TickSpar(dt, walker.Position, adultAnchor,
                Clear(position, walker.Position) && CanApproach(position, walker.Position), holds);
            for (int i = 0; i < ReprimandBeats.Length; i++)
            {
                float beat = ReprimandBeats[i];
                if (previous <= beat || reprimand > beat)
                    continue;
                if (swat != null)
                    audio.PlayOneShot(swat, .65f);
                walker.Reprimand(true, true);
                if (i == ReprimandBeats.Length - 1)
                    Hurt(70);
            }
            if (reprimand == 0f || IsCrying)
            {
                adult = null;
                walker.Reprimand(false);
            }
        }

        private void Hurt(int damage)
        {
            Health = Mathf.Max(0, Health - damage);
            if (Health != 0)
                return;
            recovery = ChildLocomotion.CryDuration;
            walker.Cry(recovery);
            PlayCry(.88f);
        }

        private void PlayCry(float volume)
        {
            if (sobs != null)
                audio.PlayOneShot(sobs, volume);
        }

        private static bool CanApproach(Vector3 from, Vector3 to)
        {
            Vector3 direction = to - from;
            if (Mathf.Abs(direction.y) >= .48f)
                return false;
            direction.y = 0f;
            return direction.sqrMagnitude > .0001f && !Physics.SphereCast(from + Vector3.up * .42f, .20f,
                direction.normalized, out _, .34f, Walker.WorldMask, QueryTriggerInteraction.Ignore);
        }

        private void Finish()
        {
            restingChild = opponent;
            rest = 4.5f;
            opponent = null;
        }

        private static bool Clear(Vector3 from, Vector3 to)
            => !Physics.Linecast(from + Vector3.up * .67f, to + Vector3.up * .67f,
                Walker.WorldMask, QueryTriggerInteraction.Ignore);
    }
}
