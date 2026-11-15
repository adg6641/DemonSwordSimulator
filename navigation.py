"""루네아가 같은 발판 길을 찾아 차례대로 점프하도록 작은 경로 그래프를 쓴다."""
from heapq import heappush,heappop
from math import sqrt
from player import Player


def jump_reach(rise):
    remaining=Player.JUMP_SPEED**2-2*Player.GRAVITY*(rise+5)
    if remaining<=0:
        return 0
    return Player.AIR_SPEED*(Player.JUMP_SPEED+sqrt(remaining))/Player.GRAVITY

def waypoint(scene,actor,target_x,target_y):
    platforms=scene.solid_platforms()
    goal=next((i for i,o in enumerate(platforms) if abs(o['y']-target_y)<3 and scene.platform_span(o)[0]<=target_x<=scene.platform_span(o)[1]),None)
    if goal is None:return target_x,target_y
    source=next((i for i,o in enumerate(platforms) if abs(o['y']-actor.y)<3 and scene.platform_span(o)[0]<=actor.x<=scene.platform_span(o)[1]),-1)
    if source==goal:return target_x,target_y
    distances={source:0}; paths={source:[]}; queue=[(0,source)]
    while queue:
        cost,i=heappop(queue)
        if cost>distances[i]:continue
        if i==goal:
            first=platforms[paths[i][0]]
            left,right=scene.platform_span(first)
            x=max(left+24,min(right-24,actor.x))
            y=0 if source==-1 else platforms[source]['y']
            reach=jump_reach(first['y']-y)
            # Walk near the lip before jumping, then aim for the near side of the next plank.
            approach=x-max(-1,min(1,x-actor.x))*max(40,reach-60)
            if source!=-1:
                lo,hi=scene.platform_span(platforms[source])
                approach=max(lo+20,min(hi-20,approach))
            if abs(x-actor.x)>max(52,reach-38) and abs(approach-actor.x)>16:
                return approach,y
            return x,first['y']
        x,y=(actor.x,0) if i==-1 else (platforms[i]['x'],platforms[i]['y'])
        source_left,source_right=(x,x) if i==-1 else scene.platform_span(platforms[i])
        for j,o in enumerate(platforms):
            if j==i:continue
            dy=o['y']-y
            gap=abs(o['x']-x)
            # 지상에서는 걸어서 접근하고, 위에서는 한 번에 뛸 수 있는 발판만 잇는다.
            if i==-1:
                allowed=0<o['y'] and jump_reach(dy)>0
                step=gap/230+1
            else:
                left,right=scene.platform_span(o)
                edge_gap=max(0,left-source_right,source_left-right)
                allowed=-500<=dy and edge_gap+42<=jump_reach(dy)
                step=gap/260+max(0,dy)/170+.5
            if not allowed:continue
            new=cost+step
            if new<distances.get(j,1e9):
                distances[j]=new;paths[j]=paths[i]+[j];heappush(queue,(new,j))
    return target_x,target_y
