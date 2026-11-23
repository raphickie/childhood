"""Generate the village house surface atlas from original painted patterns."""
import math
import random

SIZE = 256
TILE = 64
MATERIALS = {
    "log": 0, "boards": 1, "end grain": 2, "gable": 3,
    "slate": 4, "steel": 5, "felt": 6, "brick": 7,
    "rubble": 8, "paint": 9, "glass": 10, "curtain": 11,
}


def atlas_uv(material, u, v):
    tile = MATERIALS[material]
    return ((tile % 4 * TILE + 1.5 + u * (TILE - 3)) / SIZE,
            (tile // 4 * TILE + 1.5 + v * (TILE - 3)) / SIZE)


def build_house_atlas():
    rng = random.Random(200609)
    pixels = bytearray([255] * (SIZE * SIZE * 4))

    for material, tile in MATERIALS.items():
        for y in range(TILE):
            for x in range(TILE):
                u, v = x / (TILE - 1), y / (TILE - 1)
                grit = rng.uniform(-.025, .025)
                wave = math.sin(11*u + 14*v) * math.sin(7*u - 24*v)
                grime = .55 + .45*math.sin(12*u + 9*v)*math.sin(7*u - 16*v)
                tint = (1, 1, 1)
                if material in ("log", "boards", "gable", "paint"):
                    knot_x, knot_y = (.67, .62) if material != "gable" else (.36, .43)
                    radius = math.hypot((u-knot_x)*1.9, (v-knot_y)*6.2)
                    whorl = math.exp(-radius * 4.3)
                    grain = math.sin(174*v + 2.7*math.sin(13*u) + 8*whorl)
                    fibre = math.sin(371*v + 2.5*math.sin(22*u))*math.sin(8*u - 5*v)
                    crack = max(0, (fibre-.79)/.21) * .17
                    shade = .92 + .051*grain + .022*wave + .021*fibre - .23*whorl - crack
                    if material == "log":
                        shade *= .72 + .28*math.sin(math.pi*v)**.48
                        tint = (1.02, .98, .94)
                    elif material == "paint":
                        shade = .88 + .31*(shade-.84) - .11*max(0, (grime-.70)/.30)
                        tint = (1, 1.01, 1.01)
                    elif material == "boards":
                        shade -= .08 * (1-v)**8
                elif material == "end grain":
                    dx, dy = (u-.46)*2, (v-.54)*2
                    radius = math.hypot(dx, dy)
                    rings = math.sin(54*radius + 2*math.sin(dx*4.5 + dy*11))
                    splits = max(0, math.cos(math.atan2(dy, dx)*5 + radius)**30 - .35)
                    shade = .93 + .056*rings - .18*radius - .20*splits*radius + .03*wave
                    tint = (1.04,.98,.91)
                elif material in ("slate", "steel", "felt"):
                    if material == "slate":
                        corrugation = .5 + .5*math.sin(6*math.tau*u + .16*math.sin(v*9))
                        shade = .70 + .21*corrugation + .04*wave - .08*grime
                        shade -= .10 * max(0, 1-10*abs(v-.92))
                        tint = (1.02,1.0,.94)
                    elif material == "steel":
                        seam = min(u,1-u)
                        shine = max(0,1-19*abs(u-.14))
                        shade = .78 + .16*min(1,16*seam) + .08*shine - .11*grime**3
                        tint = (1.01,1.02,1.04)
                    else:
                        shade = .67 + .08*wave + .14*grime
                        if min(abs(u-.08),abs(u-.92)) < .025:
                            shade += .16
                        tint = (.97,1.0,1.0)
                elif material == "brick":
                    row = math.floor(v*6)
                    ux = u*4 + .5*(row%2)
                    seam = min(ux%1, 1-ux%1, v*6%1, 1-v*6%1)
                    shade = (.69 if seam < .067 else .87 + .075*math.sin(7*row + 9*math.floor(ux))) + .058*wave
                    tint = (1.04,1.06,1.03) if seam < .067 else (1.04,.95,.88)
                elif material == "rubble":
                    ox, oy = 4*u + .08*math.sin(19*v), 3*v + .085*math.sin(32*u)
                    ox += .47*(math.floor(oy)%2)
                    seam = min(ox%1, 1-ox%1, oy%1, 1-oy%1)
                    shade = .67 if seam < .063 else .91 + .07*math.sin(6*math.floor(ox) + 13*math.floor(oy)) - .05*wave
                    tint = (1.04,1.01,.95)
                elif material == "glass":
                    sky = .54 + .27*v + .11*math.sin(4*u - v)
                    canopy = .07 * math.sin(u*17 + v*21)*math.sin(u*30 - v*13)
                    reflection = max(0, 1-18*abs(u-.15-.36*v)) * .10
                    shade = sky + canopy + reflection
                    tint = (.80,1.02,1.06)
                    grit *= .3
                else:
                    shade = .94 + .06*math.sin(u*23*math.tau) - .10*(math.sin(15*u)**2)
                    tint = (1.04,1.01,.94)
                color = bytes(min(255,max(0,round(255*(shade+grit)*channel))) for channel in tint)
                at = ((tile // 4 * TILE + y) * SIZE + tile % 4 * TILE + x) * 4
                pixels[at:at+3] = color

    return pixels
