#!/usr/bin/env python3
"""Locked R10 experiment. Run from any cwd; saves auditable, unsubmitted artifact."""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone
import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gems46.crossover import coarse_maps, score_maps, expand
from gems46 import grid, emission, metric


def read(path):
    with rasterio.open(path) as s:
        return s.read(1)


def correlation(a,b,mask):
    x,y = a[mask][::8],b[mask][::8]
    return dict(n=len(x), pearson=float(np.corrcoef(x,y)[0,1]),
                spearman=float(spearmanr(x,y).statistic))


def audit(path, template):
    with rasterio.open(path) as s, rasterio.open(template) as t:
        a=s.read(1)
        checks=dict(single_band=s.count==1,float32=s.dtypes==('float32',),
            crs=s.crs==t.crs, shape=s.shape==t.shape, transform=s.transform==t.transform,
            finite=bool(np.isfinite(a).all()), range=bool(((a>=0)&(a<=1)).all()),
            no_nodata=s.nodata is None)
        assert all(checks.values()),checks
        return dict(checks=checks, min=float(a.min()),max=float(a.max()),
            positive=int((a>0).sum()),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            pixel_sha256=hashlib.sha256(a.tobytes()).hexdigest(),bytes=path.stat().st_size,
            shape=list(s.shape),crs=str(s.crs),transform=list(s.transform))


def main():
    out=ROOT/'docs/r10'; out.mkdir(exist_ok=True)
    derived=ROOT/'data/derived'; derived.mkdir(exist_ok=True)
    raw=ROOT/'data/raw'; template=raw/'sample_submission.tif'
    # All inputs pinned before scientific use.
    manifest=json.loads((ROOT/'registry/data_manifest.json').read_text())
    hashes={}
    for item in manifest['files']:
        p=ROOT/item['dest']; sha=hashlib.sha256(p.read_bytes()).hexdigest()
        assert sha==item['sha256'],p
        hashes[item['dest']]=sha
    fp=grid.footprint(template,raw/'training_features.tif')
    cat=(read(raw/'labels.tif')>0)&fp
    exclusion=ndimage.binary_dilation(cat,iterations=2)
    domain=fp&~exclusion
    truth=(read(ROOT/'data/external/sgmc_faults_100m_u8.tif')>0)&domain
    parts=[]; support=fp.copy(); controls={}
    with rasterio.open(raw/'training_features.tif') as src:
        for band,name in [(2,'rtp'),(13,'gravity')]:
            a=src.read(band,masked=True).filled(np.nan)
            valid=fp&np.isfinite(a)
            print('DFA',name,src.descriptions[band-1],flush=True)
            maps,rows,cols=coarse_maps(a,valid)
            score,coarse_valid=score_maps(maps)
            field,good=expand(score,coarse_valid,rows,cols,a.shape)
            np.savez_compressed(derived/f'r10_{name}.npz',maps=maps,rows=rows,cols=cols,score=score)
            parts.append(field); support &= good
            # Controls avoid zero-padding artefacts by a 16px validity erosion below.
            filled=np.where(valid,a,0)
            blurred=ndimage.gaussian_filter(filled,3)
            gy,gx=np.gradient(blurred)
            controls[name+'_gradient']=np.hypot(gy,gx)
            controls[name+'_curvature']=np.abs(ndimage.laplace(blurred))
            support &= ndimage.binary_erosion(valid,iterations=16)
    field=np.where(support,np.minimum(*parts),0).astype(np.float32)
    np.save(derived/'r10_field.npy',field)
    candidate,_=emission.greedy_emit(field,domain&support,37654,min_dist=3,smooth_px=1.85)
    assert candidate.sum()==37654
    values=candidate.astype('float32')
    pixelhash=hashlib.sha256(values.tobytes()).hexdigest()
    filename=f'gems46-r10-dfa-crossover-{pixelhash[:12]}-zeros.tif'
    with rasterio.open(template) as t: profile=t.profile.copy()
    profile.update(count=1,dtype='float32',nodata=None,compress='deflate',predictor=3)
    path=out/filename
    with rasterio.open(path,'w',**profile) as dst: dst.write(values,1)
    receipt=audit(path,template)
    refs={
        'GEMSDOE32-owner-reported-02778':ROOT/'data/derived/incumbent_02778.tif',
        'H46-structural-DFA':ROOT/'docs/downloads/gems46-h46-2-dfa-corroborated-zeros.tif',
        'R8-conformal':ROOT/'SUBMISSION-GEMSDOE46-r8-conformal.tif',
        'R9-conformal':ROOT/'docs/r9/downloads/gems46-r9-conformal-s5-20261006T110804Z.tif',
        'H46-pure-DFA':ROOT/'docs/downloads/gems46-h46-1-dfa-regime-break-zeros.tif'}
    comparisons={}; fields={'R10':field}
    mask=domain&support
    smooth=ndimage.gaussian_filter(field,8)
    for name,p in refs.items():
        if not p.exists():
            comparisons[name]={'missing':True}; continue
        with rasterio.open(p) as s:
            assert s.shape==fp.shape and s.transform==profile['transform'] and s.crs==profile['crs']
        a=np.nan_to_num(read(p),nan=0,posinf=0,neginf=0)
        assert np.all((a>=0)&(a<=1))
        fields[name]=a
        assert not np.array_equal(values,a), 'candidate duplicates comparator'
        old=a>0
        comparisons[name]=dict(file=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            pixel_identical=bool(np.array_equal(values,a)),
            candidate_pearson=correlation(values,a,domain),
            field_vs_smoothed_submission=correlation(smooth,ndimage.gaussian_filter(a,8),mask),
            jaccard=float((candidate&old).sum()/max((candidate|old).sum(),1)))
    for name,a in controls.items():
        comparisons[name]=dict(raw=correlation(field,a,mask),
            smoothed=correlation(smooth,ndimage.gaussian_filter(a,8),mask))
    # Scan every shipped local raster for pixel equality, not just byte inequality.
    equality=[]
    for p in sorted(set(ROOT.glob('*.tif'))|set((ROOT/'docs').rglob('*.tif'))):
        if p==path: continue
        a=read(p)
        equality.append(dict(file=str(p.relative_to(ROOT)),equal=bool(a.shape==values.shape and np.array_equal(np.nan_to_num(a),values))))
    assert not any(x['equal'] for x in equality)
    print('Validating spatial blocks',flush=True)
    # Fixed detector, no fitting to proxy labels. Per-block common counts, exclusions and guard.
    re=np.linspace(0,fp.shape[0],5,dtype=int); ce=np.linspace(0,fp.shape[1],5,dtype=int)
    folds=[]; skipped=[]
    for i in range(4):
        for j in range(4):
            sl=np.s_[re[i]+3:re[i+1]-3,ce[j]+3:ce[j+1]-3]
            d=domain[sl]; target=truth[sl]
            if target.sum()==0 or d.sum()==0:
                skipped.append(dict(block=4*i+j,reason='no proxy truth or empty domain')); continue
            budget=int(round(37654*d.sum()/domain.sum()))
            masks={}; scores={}
            for name,f in fields.items():
                masks[name],_=emission.greedy_emit(f[sl],d,budget,min_dist=3,smooth_px=1.85)
            # Where a sparse reference cannot supply the budget, compare all at minimum count.
            n=min(int(a.sum()) for a in masks.values())
            if n==0:
                skipped.append(dict(block=4*i+j,reason='zero shared emission capacity',
                    counts={k:int(v.sum()) for k,v in masks.items()})); continue
            for name,f in fields.items():
                pred,_=emission.greedy_emit(f[sl],d,n,min_dist=3,smooth_px=1.85)
                assert pred.sum()==n
                scores[name]=metric.components_binary(pred,target,valid=d).as_dict()
            folds.append(dict(block=4*i+j,emitted_each=n,truth=int(target.sum()),scores=scores))
            print('block',4*i+j,'mass',n,'R10',scores['R10']['dti'],flush=True)
    means={n:float(np.mean([b['scores'][n]['dti'] for b in folds])) for n in fields}
    best=max((n for n in fields if n!='R10'),key=means.get)
    delta=np.array([b['scores']['R10']['dti']-b['scores'][best]['dti'] for b in folds])
    rng=np.random.default_rng(4610)
    ci=np.percentile(rng.choice(delta,(10000,len(delta)),replace=True).mean(axis=1),[2.5,97.5])
    gate=bool(not any(b['reason']=='zero shared emission capacity' for b in skipped) and len(folds)>=8 and ci[0]>0 and means['R10']>means[best] and not any(x.get('missing') for x in comparisons.values()))
    coeff=[]
    for rec in comparisons.values():
        for key in ('raw','smoothed','field_vs_smoothed_submission'):
            if key in rec: coeff += [abs(rec[key][k]) for k in ('pearson','spearman')]
    distinct=bool(coeff and np.isfinite(coeff).all() and max(coeff)<0.2)
    result=dict(experiment='H46-R10',generated_utc=datetime.now(timezone.utc).isoformat(),
        file=filename,note='R10 raw RTP/gravity DFA slope crossover, 0.8-12.8 km scales; 37,654 dots; research candidate, proxy-gated, no leaderboard score.',
        parameters=dict(window=512,stride=16,scales=[8,16,32,64,96,128],bands=[2,13],
            background_cells=31,normalization_percentile=99,budget=37654,min_dist_argument=3,
            smooth_px=1.85,catalogue_cross_dilation_iterations=2,block_grid=[4,4],guard_pixels=3,
            bootstrap_seed=4610,correlation_sampling='every eighth pixel of fixed common-valid mask'),
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
            ['scripts/run_r10.py','src/gems46/crossover.py','src/gems46/emission.py','src/gems46/metric.py']},
        input_hashes=hashes,audit=receipt,support_pixels=int(support.sum()),comparisons=comparisons,
        local_pixel_uniqueness=equality,folds=folds,skipped_blocks=skipped,mean_block_dti=means,best_comparator=best,
        paired_delta=float(delta.mean()),paired_bootstrap_95=ci.tolist(),gate_passed=gate,
        low_correlation_gate_passed=distinct,max_absolute_correlation=max(coeff),
        status='PROXY_GATE_PASSED_NOT_SUBMITTED' if gate else 'HOLD_DO_NOT_SUBMIT',
        limitations=['SGMC is an imperfect reused proxy, not hidden competition truth.',
          'Matched-mass comparator rules re-emit fields within each block; these are not scores of original files.',
          'Large overlapping DFA windows induce spatial dependence; bootstrap is descriptive, not a causal significance test.',
          'Correlation cannot establish geological independence or fault discovery.',
          'Unique against inspected local rasters and restored GEMSDOE32 only; universal uniqueness not verified.'])
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'registry/r10.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('file','mean_block_dti','paired_delta','paired_bootstrap_95','status','low_correlation_gate_passed','max_absolute_correlation')},indent=2))

if __name__=='__main__': main()
