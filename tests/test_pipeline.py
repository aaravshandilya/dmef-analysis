import unittest,tempfile,argparse
from pathlib import Path
import numpy as np
import pandas as pd
from dmef import masks,stats,train
from correct import correct

class PipelineTests(unittest.TestCase):
 def test_square_contamination(self):
  r=dict(cx=50,cy=50,rx=30,ry=30,angle=0)
  full,inner,square=masks((101,101),r,.1)
  im=np.zeros((101,101,3),np.uint8); im[full]=100
  self.assertEqual(stats(im,inner)['R_median'],100)
  self.assertGreater(square.sum(),full.sum())
  self.assertLess(im[square].mean(),im[inner].mean())
 def test_signed_background_and_missing_reference(self):
  measurements=pd.DataFrame([dict(image_id='a',well_id='W1',inner_R_median=10,inner_G_median=20,inner_B_median=30),dict(image_id='b',well_id='W1',inner_R_median=15,inner_G_median=5,inner_B_median=10)])
  labels=pd.DataFrame([dict(image_id='a',well_id='W1',blank_image_id='b',blank_well_id='W1',excitation_B=np.nan)])
  r=correct(measurements,labels).iloc[0]; self.assertEqual(r.net_R,-5); self.assertTrue(pd.isna(r.RF_B))
 def test_unlabelled_training_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp); pd.DataFrame([dict(image_id='a',well_id='W1')]).to_csv(p/'m.csv',index=False)
   pd.DataFrame([dict(image_id='a',well_id='W1',target='',experiment_id='pilot_unconfirmed')]).to_csv(p/'l.csv',index=False)
   with self.assertRaisesRegex(ValueError,'Confirmed targets'): train(argparse.Namespace(measurements=p/'m.csv',labels=p/'l.csv',output=p/'model'))
 def test_training_smoke_with_synthetic_independent_groups(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp); rows=[]; labels=[]
   for g in range(6):
    for c in range(2):
     k=dict(image_id=f'g{g}c{c}',well_id='W1'); rows.append(dict(**k,**{f'inner_{channel}_{s}':10+c*50+g for channel in 'RGB' for s in ['median','iqr']})); labels.append(dict(**k,target=f'class{c}',experiment_id=f'group{g}',reviewed=True,roi_reviewed=True))
   pd.DataFrame(rows).to_csv(p/'m.csv',index=False); pd.DataFrame(labels).to_csv(p/'l.csv',index=False)
   train(argparse.Namespace(measurements=p/'m.csv',labels=p/'l.csv',output=p/'model'))
   self.assertTrue((p/'model/model.joblib').exists())
if __name__=='__main__': unittest.main()
