"""Optional matched-blank subtraction; never substitutes the dark mounting ring."""
import argparse
import numpy as np
import pandas as pd

def correct(measurements,labels):
    keys=['image_id','well_id']; source=measurements.set_index(keys)
    df=measurements.merge(labels,on=keys,validate='one_to_one')
    for c in 'RGB': df[f'net_{c}']=np.nan
    df['RF_B']=np.nan; df['correction_status']='missing_confirmed_blank'
    for i,row in df.iterrows():
        key=(row.blank_image_id,row.blank_well_id)
        if any(pd.isna(k) for k in key): continue
        if key not in source.index: raise ValueError(f'Unknown blank: {key}')
        blank=source.loc[key]
        for c in 'RGB': df.at[i,f'net_{c}']=row[f'inner_{c}_median']-blank[f'inner_{c}_median']
        df.at[i,'correction_status']='matched_blank_subtracted_in_stored_RGB_units'
        b=pd.to_numeric(row.excitation_B,errors='coerce')
        if pd.notna(b) and b>0: df.at[i,'RF_B']=df.at[i,'net_R']/b
    return df
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--measurements',default='results/measurements.csv'); p.add_argument('--labels',default='results/labels.csv'); p.add_argument('--output',default='results/corrected.csv'); a=p.parse_args()
    correct(pd.read_csv(a.measurements),pd.read_csv(a.labels)).to_csv(a.output,index=False)
