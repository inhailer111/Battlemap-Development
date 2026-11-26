# Drop-in replacement for run_detail in ui_docks/session_controller.py
import math


def run_detail(self):
    w = Atlas.current
    if w is None or worldgen is None:
        return
    done = getattr(w, "done", None)
    if done is None:
        done = set()
        setattr(w, "done", done)
    rects = []
    if Zoom.dm >= DETAIL_ZOOM:
        rects.append(self.view_rect())
    if self.player_win is not None and Zoom.tv >= DETAIL_ZOOM:
        pv = self.player_win.view
        rects.append(pv.mapToScene(pv.viewport().rect()).boundingRect())
    ch = getattr(worldgen, "CHUNK_FT", 250)
    k, todo = UNITS_PER_FT, []
    for r in rects:
        for cx in range(math.floor(r.left() / k / ch), math.floor(r.right() / k / ch) + 1):
            for cy in range(math.floor(r.top() / k / ch), math.floor(r.bottom() / k / ch) + 1):
                if (cx, cy) not in done and (cx, cy) not in todo:
                    todo.append((cx, cy))
    numbers = {}
    for key in todo[:6]:
        self.instantiate(w.plan_chunk(*key), numbers)
        done.add(key)
    if len(todo) > 6:
        self.detail_timer.start()
