import sys, time, math
sys.path.insert(0,"/Users/cyril/src/lotusim-lab/_offline")
import cosim as C
def trial(internal_dt, comm_dt, T=6.0):
    """Commande CONSTANTE (barre à fond, écoute fixe) -> seule l'intégration diffère.
    Si xdyn subdivise, la traj dépend de internal_dt, PAS de comm_dt."""
    C.write_model(180); C.launch_xdyn(solver="rk4", dt=internal_dt)
    try:
        time.sleep(4); sock=C.ws_connect("127.0.0.1",12345)
        st=C.init_at(C.CLOSE_HAULED,0.8)
        helm=C.HELM_MAX; sheet=C.opt_sheet(60.0); div=False
        for i in range(int(T/comm_dt)):
            try: st=C.step(sock, st, sheet, helm, comm_dt)
            except RuntimeError: div=True; break
        if div: return (internal_dt,comm_dt,"DIVERGE",None,None,None)
        return (internal_dt, comm_dt, f"{math.degrees(C.yaw_of(st)):.1f}",
                f"{st['x']:.2f}", f"{st['y']:.2f}", f"{st['u']:.2f}")
    finally: C.stop_xdyn()
print(f"{'internal':>9} {'comm':>6} | {'yaw_fin':>8} {'x':>6} {'y':>6} {'u':>5}")
for idt,cdt in [(0.02,0.02),(0.001,0.001),(0.001,0.02),(0.02,0.001)]:
    r=trial(idt,cdt)
    print(f"{r[0]:>9} {r[1]:>6} | {r[2]:>8} {str(r[3]):>6} {str(r[4]):>6} {str(r[5]):>5}")
