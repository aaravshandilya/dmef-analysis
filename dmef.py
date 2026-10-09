"""DMEF pilot: reviewable circular image measurements and grouped classification."""
import argparse, hashlib, json, io
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageCms
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def read_rgb(path):
    im=Image.open(path); icc=im.info.get('icc_profile')
    im=ImageOps.exif_transpose(im).convert('RGB')
    if icc: im=ImageCms.profileToProfile(im,ImageCms.ImageCmsProfile(io.BytesIO(icc)),ImageCms.createProfile('sRGB'),outputMode='RGB')
    return np.asarray(im), 'ICC converted to sRGB' if icc else 'untagged; color space unverified'

def detect(rgb):
    scale=min(1.,1200/max(rgb.shape[:2])); small=cv2.resize(rgb,None,fx=scale,fy=scale)
    hsv=cv2.cvtColor(small,cv2.COLOR_RGB2HSV)
    mask=cv2.inRange(hsv,np.array([12,60,130]),np.array([48,255,255]))
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    result=[]; h,w=small.shape[:2]
    for c in contours:
        a=cv2.contourArea(c); p=cv2.arcLength(c,True)
        if not .002*h*w<a<.09*h*w or len(c)<5 or p==0: continue
        circ=4*np.pi*a/p**2; (x,y),(aw,bh),ang=cv2.fitEllipse(c)
        if circ<.7 or min(aw,bh)/max(aw,bh)<.72: continue
        result.append(dict(cx=x/scale,cy=y/scale,rx=aw/2/scale,ry=bh/2/scale,angle=ang,circularity=circ))
    result.sort(key=lambda z:z['cy'])
    if len(result)==4: result=sorted(result[:2],key=lambda z:z['cx'])+sorted(result[2:],key=lambda z:z['cx'])
    return result

def masks(shape,r,shrink):
    y,x=np.ogrid[:shape[0],:shape[1]]; a=np.deg2rad(r['angle']); dx=x-r['cx']; dy=y-r['cy']
    u=dx*np.cos(a)+dy*np.sin(a); v=-dx*np.sin(a)+dy*np.cos(a)
    distance=(u/r['rx'])**2+(v/r['ry'])**2
    ex=np.hypot(r['rx']*np.cos(a),r['ry']*np.sin(a)); ey=np.hypot(r['rx']*np.sin(a),r['ry']*np.cos(a)); half=max(ex,ey)
    return distance<=1,distance<=(1-shrink)**2,(abs(dx)<=half)&(abs(dy)<=half)

def stats(rgb,mask):
    v=rgb[mask]
    if not len(v): raise ValueError('Empty ROI')
    med=np.median(v,axis=0); iqr=np.percentile(v,75,axis=0)-np.percentile(v,25,axis=0)
    return {**{f'{c}_median':float(med[i]) for i,c in enumerate('RGB')},**{f'{c}_iqr':float(iqr[i]) for i,c in enumerate('RGB')},'pixel_count':len(v)}

def analyze(args):
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    override=json.loads(Path(args.rois).read_text()) if args.rois else {}; rows=[]; found={}; inventory=[]
    for path in sorted(Path(args.input).iterdir()):
        if path.suffix.lower() not in ['.jpg','.jpeg','.png','.tif','.tiff']: continue
        rgb,color=read_rgb(path); ident=path.stem; rois=override.get(ident,detect(rgb)); found[ident]=rois
        dest=out/ident; dest.mkdir(exist_ok=True); overlay=rgb.copy(); gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
        candidate=(np.abs(gray.astype(float)-cv2.medianBlur(gray,9).astype(float))>25)|(rgb.max(axis=2)>=250)
        Image.fromarray(rgb).save(dest/'analysis.png')
        inventory.append(dict(image_id=ident,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),width=rgb.shape[1],height=rgb.shape[0],detected_wells=len(rois),color_status=color))
        for j,r in enumerate(rois,1):
            full,inner,square=masks(rgb.shape,r,args.edge_fraction); clean=inner&~candidate
            if not clean.any(): clean=inner.copy()
            wid=f'W{j:02d}'; mask=np.zeros(inner.shape,np.uint8); mask[full&~inner]=1; mask[inner]=2; mask[inner&candidate]=3
            Image.fromarray(mask).save(dest/f'{wid}_mask.png')
            data=dict(image_id=ident,well_id=wid,edge_fraction=args.edge_fraction,candidate_fraction=float((candidate&inner).sum()/inner.sum()),saturated_fraction=float(((rgb.max(axis=2)==255)&inner).sum()/inner.sum()),qc_status='needs_review',**r)
            variants={'square':square,'circle':full,'inner':inner,'candidate_excluded':clean}
            for name,m in variants.items(): data.update({f'{name}_{k}':v for k,v in stats(rgb,m).items()})
            for frac in [0,.05,.1,.15]:
                _,m,_=masks(rgb.shape,r,frac); data.update({f'edge{int(frac*100)}_{k}':v for k,v in stats(rgb,m).items() if k.endswith('median')})
            rows.append(data); overlay[full&~inner]=(0.5*overlay[full&~inner]+.5*np.array([20,100,255])).astype('uint8'); overlay[inner&candidate]=[255,0,255]
            cv2.ellipse(overlay,((r['cx'],r['cy']),(2*r['rx'],2*r['ry']),r['angle']),(0,255,0),3)
            cv2.putText(overlay,wid,(int(r['cx']),int(r['cy'])),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
            fig,ax=plt.subplots(figsize=(6,4))
            for name in variants: ax.plot(list('RGB'),[data[f'{name}_{c}_median'] for c in 'RGB'],marker='o',label=name)
            ax.set(title=f'{ident} / {wid}',ylabel='Stored RGB channel value (0–255)',ylim=(0,255)); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(dest/f'{wid}_rgb.png'); plt.close(fig)
        thumb=Image.fromarray(overlay); thumb.thumbnail((1000,1000)); thumb.save(dest/'review.png')
    pd.DataFrame(rows).to_csv(out/'measurements.csv',index=False); pd.DataFrame(inventory).to_csv(out/'inventory.csv',index=False)
    (out/'rois.json').write_text(json.dumps(found,indent=2))
    metadata=pd.DataFrame(rows)[['image_id','well_id']].copy()
    for col,val in dict(experiment_id='pilot_unconfirmed',target='',reviewed=False,roi_reviewed=False,blank_image_id='',blank_well_id='',excitation_B='').items(): metadata[col]=val
    if not (out/'labels.csv').exists(): metadata.to_csv(out/'labels.csv',index=False)
    (out/'run.json').write_text(json.dumps(dict(edge_fraction=args.edge_fraction,status='unreviewed measurements; no biological model fitted',images=len(inventory),wells=len(rows)),indent=2))
    print(f'Analyzed {len(inventory)} images; {len(rows)} candidate wells. Review before use.')

def train(args):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold,cross_val_predict
    from sklearn.metrics import balanced_accuracy_score,classification_report
    import joblib
    df=pd.read_csv(args.measurements); labels=pd.read_csv(args.labels); keys=['image_id','well_id']
    if labels.duplicated(keys).any() or df.duplicated(keys).any(): raise ValueError('Duplicate well keys')
    
    if set(map(tuple,df[keys].to_numpy()))!=set(map(tuple,labels[keys].to_numpy())): raise ValueError('Measurements and labels must contain exactly the same well keys')
    df=df.merge(labels,on=keys,validate='one_to_one')
    if df.empty or df[['target','experiment_id']].isna().any().any(): raise ValueError('Confirmed targets and experiment IDs required. No model fitted.')
    if not all(df[c].astype(str).str.lower().eq('true').all() for c in ['reviewed','roi_reviewed']): raise ValueError('Every row needs label and ROI review.')
    if df.experiment_id.str.contains('unconfirmed',case=False).any(): raise ValueError('Replace placeholder experiment IDs; repeated captures belong together.')
    if df.target.nunique()<2: raise ValueError('Classification needs at least two confirmed classes.')
    if df.groupby('target').experiment_id.nunique().min()<3: raise ValueError('Need at least three independent experiments per class for grouped pilot validation.')
    features=[f'inner_{c}_{s}' for c in 'RGB' for s in ['median','iqr']]; X=df[features]; y=df.target.astype(str); groups=df.experiment_id
    splits=list(StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=42).split(X,y,groups))
    for tr,te in splits:
        if set(groups.iloc[tr])&set(groups.iloc[te]): raise ValueError('Group leakage')
        if set(y.iloc[tr])!=set(y): raise ValueError('Training fold lacks a class; add experiments.')
    model=make_pipeline(StandardScaler(),LogisticRegression(class_weight='balanced',max_iter=2000,random_state=42)); pred=cross_val_predict(model,X,y,cv=splits)
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    report=dict(balanced_accuracy=balanced_accuracy_score(y,pred),classification_report=classification_report(y,pred,output_dict=True,zero_division=0),validation='3-fold experiment-grouped development estimate; not external validation',features=features)
    (out/'metrics.json').write_text(json.dumps(report,indent=2)); pd.DataFrame({'truth':y,'prediction':pred,'experiment_id':groups}).to_csv(out/'validation_predictions.csv',index=False)
    model.fit(X,y); joblib.dump(dict(model=model,features=features),out/'model.joblib'); print(json.dumps(report,indent=2))

def predict(args):
    import joblib
    bundle=joblib.load(args.model) # Only load trusted model files.
    df=pd.read_csv(args.measurements); result=df[['image_id','well_id']].copy(); result['prediction']=bundle['model'].predict(df[bundle['features']]); result.to_csv(args.output,index=False)

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('analyze'); a.add_argument('--input',default='data/raw'); a.add_argument('--output',default='results'); a.add_argument('--rois'); a.add_argument('--edge-fraction',type=float,default=.1)
    t=sub.add_parser('train'); t.add_argument('--measurements',default='results/measurements.csv'); t.add_argument('--labels',default='results/labels.csv'); t.add_argument('--output',default='models')
    q=sub.add_parser('predict'); q.add_argument('--model',default='models/model.joblib'); q.add_argument('--measurements',default='results/measurements.csv'); q.add_argument('--output',default='predictions.csv')
    args=p.parse_args()
    if args.cmd=='analyze' and not 0<=args.edge_fraction<.5: p.error('edge-fraction must be between 0 and 0.5')
    {'analyze':analyze,'train':train,'predict':predict}[args.cmd](args)
if __name__=='__main__': main()
