"""Generate the game's original sobbing and cartoon swat sounds."""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 12000
DURATION = 3.42
rng = random.Random(148)
bursts = ((.22,.42,342),(.83,.48,384),(1.48,.48,320),(2.16,.51,348),(2.86,.38,295))
breaths = ((.07,.13),(.70,.12),(1.36,.11),(2.00,.15),(2.70,.15))
resonances = ((690,.94,.63),(1250,.91,.43),(2390,.88,.24),(3150,.80,.10))
filters = [(2*r*math.cos(math.tau*f/RATE),-r*r,1-r,gain) for f,r,gain in resonances]
history = [[0.,0.] for _ in filters]
output = []
phase = 0.
previous_noise = 0.
for i in range(round(DURATION*RATE)):
    t = i/RATE
    noise = rng.uniform(-1,1)
    air = noise - .61*previous_noise
    previous_noise = noise
    voiced = 0.
    for start,length,pitch in bursts:
        u = (t-start)/length
        if not 0 < u < 1:
            continue
        f = pitch*(1.10-.33*u+.066*math.sin(math.tau*7.2*t)+.032*noise)
        phase = (phase+f/RATE)%1
        glottis = sum(math.sin(math.tau*phase*h)/(h**1.19) for h in range(1,10))
        tremble = .69+.25*math.sin(math.tau*(7.8*t+1.7*u))+.06*noise
        envelope = math.sin(math.pi*u)**1.22 * (1-.45*u)
        voiced = envelope*(tremble*glottis+.22*air)
    inhale = sum(.26*math.sin(math.pi*u)**1.75 for start,length in breaths
                 if 0 < (u := (t-start)/length) < 1)
    sample = .15*voiced + inhale*air
    for (a,b,d,gain), state in zip(filters, history):
        resonant = a*state[0]+b*state[1]+d*voiced
        state[1],state[0]=state[0],resonant
        sample += gain*resonant
    output.append(sample)

normalization = .76/max(abs(x) for x in output)
path = Path(__file__).resolve().parents[1]/"Assets"/"Resources"/"Crying.wav"
with wave.open(str(path),"wb") as wav:
    wav.setparams((1,2,RATE,0,"NONE","not compressed"))
    wav.writeframes(b"".join(struct.pack("<h",round(s*normalization*32767)) for s in output))

with wave.open(str(path.with_name("Swat.wav")), "wb") as wav:
    wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
    samples = bytearray()
    previous = 0.
    for i in range(round(.11 * RATE)):
        t = i / RATE
        noise = rng.uniform(-1, 1)
        tick = (noise - .52 * previous) * math.exp(-82 * t)
        thump = math.sin(math.tau * 234 * t) * math.exp(-38 * t)
        value = (.52 * tick + .38 * thump) * min(1, t / .0018)
        samples.extend(struct.pack("<h", round(value * 27000)))
        previous = noise
    wav.writeframes(samples)
