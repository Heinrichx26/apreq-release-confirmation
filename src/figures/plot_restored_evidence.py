"""Plot saved numerical evidence. No optimization or data collection is run."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/figures'
ART = ROOT / 'results/figures'
INPUTS = {}
COLORS = ['#245A81', '#BF6537', '#478372']
plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 9.5,
                     'axes.titlesize': 10, 'axes.labelsize': 9.5,
                     'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.linewidth': .7, 'xtick.labelsize': 9, 'ytick.labelsize': 9})


def read(name):
    p = ROOT / name
    INPUTS[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text(encoding='utf-8'))


def finish(fig, axes, name):
    for ax in axes:
        ax.grid(axis='y', color='#D4D8DC', lw=.5, alpha=.7)
        ax.set_axisbelow(True)
        ax.tick_params(length=3, width=.65)
    for extension in ('pdf', 'svg'):
        path = OUT / f'{name}.{extension}'
        fig.savefig(path, bbox_inches='tight', pad_inches=.04)
        if ART.resolve() != OUT.resolve():
            shutil.copy2(path, ART / path.name)
    fig.savefig(OUT / f'{name}.png', dpi=180, bbox_inches='tight', pad_inches=.04)
    plt.close(fig)


def request_order():
    data = read('results/trb_external_error_20261030/decision_trace.json')
    assert data['passed'] and data['condition']['delay']==2
    six, exact = data['six_trace'], data['exact_same_calendar_trace']
    assert all(a['reference']==b['reference'] for a,b in zip(six,exact))
    area = sum(a['release']-b['release'] for a,b in zip(six,exact))*2
    assert area==42 and six[3]['release']==10 and exact[3]['release']==8
    fig, axes = plt.subplots(1,2,figsize=(7.15,3.65),gridspec_kw={'width_ratios':[1,1.25]})
    left, right = axes
    for trace, color, ys, prefix in [(six,COLORS[0],[5,4,3],'Six-step'),
                                      (exact,COLORS[1],[1,0,-1],'Exact')]:
        requests = [(r['t'],j) for r in trace for j in r['requests']]
        assert len(requests)==3 and sorted(j for _,j in requests)==[6,8,9]
        for (t,j), y in zip(requests,ys):
            sent, received = t*2, (t+2)*2
            left.plot([sent,received],[y,y],color=color,lw=1.6)
            left.plot(sent,y,'o',ms=5,color=color)
            left.plot(received,y,'s',ms=5,mfc='white',mec=color,mew=1.3)
            value=data['service'][j]+data['report_residuals'][str(j)]
            left.text(received+.3,y,str(value),va='center',fontsize=8.5,color=color)
        left.text(9.2,ys[0]-.2,prefix,ha='right',va='bottom',fontsize=9,color=color)
    left.set(yticks=[5,4,3,1,0,-1],yticklabels=['16','12','18','12','18','16'],
             ylabel='Service interval (min)',xlim=(-.6,9.6),ylim=(-1.7,6.0),
             xticks=[0,2,4,6,8],xlabel='Request and answer time (min)')
    left.set_title('(a) Three requests in different orders',pad=10)
    t=np.arange(len(six))*2
    a=np.array([r['release'] for r in six]);b=np.array([r['release'] for r in exact])
    right.step(t,a,where='post',lw=1.8,color=COLORS[0],label='Six-step lookahead')
    right.step(t,b,where='post',lw=1.8,ls='--',color=COLORS[1],label='Exact selection')
    right.fill_between(t,a,b,step='post',color=COLORS[1],alpha=.15)
    departures=[r['reference'] for r in six]
    right.step(np.r_[0,(np.arange(len(six))+1)*2],np.r_[0,departures],where='post',
               lw=1.4,color='#53606A',ls=':',label='Takeoffs (both policies)')
    right.set(xlim=(0,68),ylim=(0,20.2),xticks=[0,12,24,36,48,60],yticks=[0,4,8,12,16,20],
              xlabel='Time since operation began (min)',ylabel='Cumulative aircraft')
    right.set_title('(b) Releases and common takeoffs',pad=10)
    right.text(.98,.08,'42 aircraft-min\nless post-release time',transform=right.transAxes,
               ha='right',va='bottom',fontsize=9,color=COLORS[1])
    left.legend(handles=[Line2D([],[],color='#53606A',marker='o',ls='',label='Request sent'),
                         Line2D([],[],color='#53606A',marker='s',mfc='white',ls='',label='Answer received')],
                loc='upper center',bbox_to_anchor=(.5,-.25),ncol=1,frameon=False,fontsize=9)
    right.legend(loc='upper center',bbox_to_anchor=(.5,-.25),frameon=False,fontsize=9)
    fig.subplots_adjust(left=.09,right=.988,top=.87,bottom=.34,wspace=.43)
    finish(fig, axes, 'request_order_effect')
    return {'additional_gate_holding_aircraft_minutes':area,'requests_on_each_history':3,
            'reference_takeoffs':data['condition']['n'],'first_difference_minutes':6,
            'six_step_postrelease_aircraft_minutes':data['six_worst_value']*2,
            'exact_postrelease_aircraft_minutes':data['exact_same_calendar_value']*2}


def calibration():
    data=read('results/trb_transfer_20261030/calibrated_full.json')
    summary=read('results/trb_transfer_20261030/summary.json')
    assert data['passed'] and len(data['rows'])==1855
    rows=data['rows'];names=['raw','calibrated90','calibrated'];labels=['Training range','90% calibration','95% calibration']
    airports=['ATL','CLT','DFW'];common=[r for r in rows if all(r[n]['reference_completes_group'] and r[n]['takeoffs_preserved'] for n in names)]
    assert len(common)==1796
    fig,axes=plt.subplots(1,3,figsize=(7.15,3.35))
    x=np.arange(3);width=.24;records={}
    for i,(name,label,color) in enumerate(zip(names,labels,COLORS)):
        coverage=[];failures=[]
        for airport in airports:
            part=[r for r in rows if r['airport']==airport]
            windows={(r['day'],r['hour']):r[name]['covered'] for r in part}
            coverage.append(sum(windows.values())/len(windows)*100)
            failures.append(sum(not r[name]['takeoffs_preserved'] for r in part))
        holding=float(np.mean([r[name]['gateholding_aircraftslots']*120/r['n'] for r in common]))
        records[name]={'covered_percent':coverage,'shortfall_settings':failures,'matched_gate_holding_seconds':holding}
        axes[0].bar(x+(i-1)*width,coverage,width,color=color)
        bars=axes[1].bar(x+(i-1)*width,failures,width,color=color)
        for bar,value in zip(bars,failures):
            axes[1].text(bar.get_x()+bar.get_width()/2,value+.45,str(value),ha='center',fontsize=8.5)
        axes[2].bar(i,holding,.63,color=color)
        axes[2].text(i,holding+3,f'{holding:.1f}',ha='center',fontsize=9)
    for ax in axes[:2]:ax.set(xticks=x,xticklabels=airports)
    axes[0].set(ylabel='Covered service windows (%)',ylim=(0,105),yticks=[0,25,50,75,100])
    axes[1].set(ylabel='Settings with shortfalls',ylim=(0,23),yticks=[0,5,10,15,20])
    axes[2].set(ylabel='Gate holding (s/aircraft)',ylim=(0,140),yticks=[0,40,80,120],
                xticks=x,xticklabels=['Training','90%','95%'])
    for ax,title in zip(axes,['(a) Service coverage','(b) Takeoff shortfalls','(c) Waiting at gates']):ax.set_title(title,pad=10)
    fig.legend(handles=[Patch(facecolor=c,label=l) for c,l in zip(COLORS,labels)],
               loc='lower center',bbox_to_anchor=(.52,-.005),ncol=3,frameon=False,
               handlelength=1.3,columnspacing=1.5,fontsize=9)
    fig.subplots_adjust(left=.077,right=.989,bottom=.235,top=.855,wspace=.58)
    finish(fig,axes,'service_calibration_effect')
    assert sum(records['raw']['shortfall_settings'])==47
    assert sum(records['calibrated']['shortfall_settings'])==1
    return {'common_complete_preserved_settings':len(common),'rules':records}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
    report={'passed':True,'saved_results_only':True}
    if True:
        report.update(request_order=request_order(),calibration=calibration())
    report['inputs_sha256']=INPUTS
    name='smoke.json' if args.smoke else 'figure_checks.json'
    (OUT/name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()


