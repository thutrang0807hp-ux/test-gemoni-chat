import io,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from browser_bridge import GeminiWorkspace
from PIL import Image
class Multi(unittest.TestCase):
 def test_order_legacy_and_cleanup(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);work=GeminiWorkspace(root);work.start=lambda **kwargs:None
   paths=[]
   for i,c in enumerate(['red','blue','green','yellow','white']):
    p=root/f'{i}.png';Image.new('RGB',(50,50),c).save(p);paths.append(p)
   calls=[]
   def request(action,**values):
    self.assertEqual(action,'image');refs=values.get('references',[]);calls.append(refs)
    for i,p in enumerate(refs):
     with Image.open(p) as image:
      actual=image.getpixel((0,0));expected=Image.open(paths[i]).getpixel((0,0));self.assertLess(max(abs(a-b)for a,b in zip(actual,expected)),5)
    Image.new('RGB',(25,25),'purple').save(values['output'],format='PNG');return {'saved':True}
   work.request=request
   self.assertTrue(work.create_image('V6 '+('x'*20000),references=paths))
   self.assertEqual(len(calls[-1]),5)
   self.assertTrue(all(not Path(p).exists()for p in calls[-1]))
   work.create_image('single legacy',reference=paths[0]);self.assertEqual(len(calls[-1]),1)
   work.create_image('prompt only');self.assertEqual(calls[-1],[])
if __name__=='__main__':unittest.main()
