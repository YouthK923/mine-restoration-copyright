# -*- coding: utf-8 -*-
# 按论文4.2节方法，从表5原始数据独立重算各微地质单元得分与最终得分

def pos(x, ideal):  # 正向指标：min=x/ideal, 上限1
    return min(x/ideal, 1.0)

def neg(x, extreme):  # 负向(污染)指标：1-x/extreme, 下限0
    return max(1.0 - x/extreme, 0.0)

def slope_score(x, mode='ratio'):
    if x <= 25:
        return 1.0
    if mode == 'ratio':      # 超过25度按 25/x 折减
        return 25.0/x
    if mode == 'linear90':   # 25~90线性折减
        return (90.0-x)/(90.0-25.0)

# 重金属极值 (CJ/T340 IV级最高值): Cd,Hg,Pb,Cr,As,Ni,Cu,Zn
EXT = dict(Cd=2, Hg=2, Pb=530, Cr=400, As=45, Ni=220, Cu=600, Zn=800)

def pollution(conc, missing=('Cr','Zn')):
    # 未检测的Cr、Zn按无污染(=1)处理
    tot = 0.0
    for k in EXT:
        if k in conc:
            tot += neg(conc[k], EXT[k])
        elif k in missing:
            tot += 1.0
    return tot/8.0

def ph_score(x, lo=5, hi=9, tol_hi=10, tol_lo=4):
    if lo <= x <= hi:
        return 1.0
    if x > hi:
        return max((tol_hi-x)/(tol_hi-hi), 0)
    return max((x-tol_lo)/(lo-tol_lo), 0)

# ---------- 原始数据(表5) ----------
data = {
 'rock': {  # 岩质边坡：无土壤指标
    'cover':68.88, 'div':0.0, 'slope':63.33, 'aspect':0.6},
 'gravel':{ # 碎石边坡
    'tr':0.34,'thick':10,'ph':9.24,'om':4.89,
    'poll':dict(Hg=0.05,As=5.17,Ni=12.60,Cu=11.70,Cd=0.04,Pb=6.50),
    'cover':87.92,'div':0.60,'slope':28.75,'aspect':0.2},
 'plat':{   # 平台：无地形指标
    'tr':0.56,'thick':30,'ph':8.72,'om':10.92,
    'poll':dict(Hg=0.02,As=3.13,Ni=12.33,Cu=11.14,Cd=0.09,Pb=9.98),
    'cover':58.42,'div':0.72},
}

for smode in ['ratio','linear90']:
    print('===== 坡度折减模式:', smode, '=====')
    # 岩质边坡: 植被0.45(覆盖0.67/多样0.33), 地形0.55(坡度0.64/坡向0.36)
    d=data['rock']
    veg = 0.67*pos(d['cover'],75) + 0.33*pos(d['div'],0.7)
    ter = 0.64*slope_score(d['slope'],smode) + 0.36*d['aspect']
    rock = 0.45*veg + 0.55*ter
    print('岩质: 植被=%.3f 地形=%.3f 单元=%.3f (表中0.56)'%(veg,ter,rock))

    # 碎石边坡: 土壤0.44 植被0.31 地形0.25
    d=data['gravel']
    pol=pollution(d['poll'])
    soil=0.25*pos(d['tr'],0.8)+0.25*pos(d['thick'],20)+0.17*ph_score(d['ph']) \
        +0.17*pos(d['om'],30)+0.17*pol
    veg =0.64*pos(d['cover'],75)+0.36*pos(d['div'],0.7)
    ter =0.67*slope_score(d['slope'],smode)+0.33*d['aspect']
    gravel=0.44*soil+0.31*veg+0.25*ter
    print('碎石: 土壤=%.3f(污染=%.3f) 植被=%.3f 地形=%.3f 单元=%.3f (表中0.74)'%(soil,pol,veg,ter,gravel))

    # 平台: 土壤0.54 植被0.46
    d=data['plat']
    pol=pollution(d['poll'])
    soil=0.25*pos(d['tr'],0.8)+0.25*pos(d['thick'],20)+0.17*ph_score(d['ph']) \
        +0.17*pos(d['om'],30)+0.17*pol
    veg =0.61*pos(d['cover'],75)+0.39*pos(d['div'],0.7)
    plat=0.54*soil+0.46*veg
    print('平台: 土壤=%.3f(污染=%.3f) 植被=%.3f 单元=%.3f (表中0.85)'%(soil,pol,veg,plat))

    final=0.1386*rock+0.6295*gravel+0.2319*plat
    print('>>> 最终得分(独立重算)= %.3f ; 用表中单元得分加权=%.4f ; 表中写0.76\n'%(final,0.740561))
