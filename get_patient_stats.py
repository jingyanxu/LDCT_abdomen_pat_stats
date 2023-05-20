

import numpy as np
import glob
import pydicom as dicom
#import tqdm
import struct 
import pandas as pd

#from scipy import ndimage
from sys import argv, exit
from optparse import OptionParser
import os
import re
import array 

from mpl_toolkits.mplot3d import Axes3D

import matplotlib.pyplot as plt
import pydicom as dicom
#plt.rcParams['image.interpolation'] = 'nearest'
#plt.rcParams['image.cmap'] = 'gray'


os.environ['PYTHONINSPECT'] = '1'

id_tags = {'name' : 0x00100010,
        'id':  0x00100020, 
        'sex' : 0x00100040,  
        'age' : 0x00101010,  
        'vendor' : 0x00080070,  
        'mA' : 0x00181151,  
        'model' : 0x00081090,  
        }
geom_tags =  { 
          'rows': 0x00280010,    # string
          'cols': 0x00280011,    # string
          'kvp': 0x00180060,    # DS 
          'diam': 0x00180090,    # DS 
          'rot_time': 0x00181150,    # DS 
          'slice_spacing': 0x00180088,    # DS 
          'rFOV' : 0x00081090,  
          'slice_thickness': 0x00180050,    # DS 
          'rFOV' : 0x00181100,  
          'table_speed' : 0x00189309,  
          'pitch_mm' : 0x00189310,  
          'pitch' : 0x00189311,     # float
          'pixel_size' : 0x00280030,     # float
          } 
rescale_tags  = {
        'intercept' :   0x00281052,     # string
        'slope' :   0x00281053,         # string
         } 

# private tags for projection data 
private_det_tags = { 
          'num_det_rows' : 0x70291010,       # unsigned int
          'num_det_cols' : 0x70291011,       # unsigned int
          'det_spacing_du' : 0x70291002,       #  fl, float single  mm
          'det_spacing_dv' : 0x70291006,       # fl, float single mm
          'det_shape' : 0x7029100b,       # string 
        }
private_src_tags = { 
          'src_angle' : 0x70311001,       # float single,  rad  x-ray source position 
          'src_z' : 0x70311002,       # float single, mm  , x-ray source position 
        }
private_acq_tags = { 
          's2o' :  0x70311003,      # source/focal to obj mm
          's2d' :  0x70311031,      # source/focal to detector mm
          'center_detector' :  0x70311033,  #  rojection from source to iso on detector  [colidx, rowidx] 
          'phiffs_dphi' :  0x7033100b,  #  in plane ffs phi offset , rad 
          'zffs_dz' :  0x7033100c,  #  zffs z offset , mm 
          'phiffs_drho' :  0x7033100d,  #  in plane ffs rho offset (radial distance), mm 
          'ffsmode' : 0x7033100e, # string, 'FFSNONE', 'FFSZ', (z-only) 'FFSXY', (in-plane only) 'FFSXYZ'
          'num_angles_per_rotation' : 0x70331013  ,   # uint
          'axial_or_helical' : 0x70371009 ,  #  string
          'photon_statistics' : 0x70331065 ,  #  array 
          'water_attenuation' : 0x70411001 ,   # string  mm-1
        }



def unpack_array (string ) : 
  u = array.array ('f') 
  a =  u.frombytes (string)  
  return  np.array (u)  
   
#  ds [private_acq_tags['center_detector']].value )
def unpack_float (string) : 
  return struct.unpack ('f', string) [0]

def unpack_uint (string) :  
  return struct.unpack ( 'H', string ) [0]

if (len(argv) < 2):
	print ("usage: get_patient_stats.py blah" )
	exit(1)

parser = OptionParser()
parser.add_option("-t, "--test", action = "store_false", dest="test", \
    help="test help mesage", default=True)

(options, args) = parser.parse_args()

outfname = args[0] 

datadir = r"D:\data\jxu\public-dataset\TCIA\manifest-1678314439739\LDCT-and-Projection-data" 
#patid = 'L019/proj/Full-dose-projections/' 

dirnames = glob.glob ( '{}/L???'.format (datadir ))  
dirnames.sort () 
print ('# of directories {}'.format ( len (dirnames)) )

pat_summary =  (  {
    'name' : [], 
    'sex' : [], 
    'age' : [], 
    #'vendor' : [], 
    'model' : [], 
    'kvp' : [], 
    'diam' : [], 
    'mA' : [], 
    'rottime' : [], 
    'table_speed' : [], 
    'pitch_mm' : [], 
    '# images' : [], 
    'rFOV' : [], 
    'pixel_mm' : [], 
    'pitch' : [], 
    'rows' : [], 
    'cols' : [], 
    'ffs' : [], 
    's2o' : [], 
    's2d' : [], 
    '2pi_views' : [], 
    #'reconfov' : [], 
    'du' : [], 
    'dv' : [], 
    'shape' : [], 
    'z_first' : [], 
    'z_last' : [], 
    'z_diff' : [], 
    '# projs' : [], 
      } )

df = pd.DataFrame (pat_summary)


for idir in dirnames [:10] :
  patid = idir.split ('\\') [-1]
  print ('working on {}'.format ( patid  ) )
  #dir_list = next(os.walk(idir))
  #dir_list = [os.path.split(r)[-1] for r, d, f in os.walk(idir) if not d]

  dir_list = list ()
  for root, dirs, files in os.walk (idir) : 
    if files and not dirs   : 
      dir_list.append (root)   

  print ('total sub dirs {}'.format  ( len (dir_list)) )
  for isubdir in dir_list : 
    tail_part = isubdir .split ('\\') [-1] 
    if (tail_part.lower ().find ('low') >=0 ) :   
      continue
    if (tail_part.lower ().find ('images') >= 0) : 
      print ('working on images in {}'.format ( tail_part )  ) 
      is_proj = False 

    if (tail_part.lower ().find ('proj') >= 0) : 
      print ('working on proj in {}'.format ( tail_part ) ) 
      is_proj = True 

    is_image = not is_proj  

    fnames = glob.glob('{}/*.dcm'.format ( isubdir ) ) 
    fnames.sort () 
    total_files = len(fnames ) 
    print ('total files {}'.format (total_files ) )

    for iname in fnames [:1] : 
  # each view will serve a number of slices 
      ds = dicom.dcmread (iname)
      if is_image : 
        patname  = ''.join ( ds[id_tags['name']].value  )
        sex  = ds[id_tags['sex']].value 
        age  = ds[id_tags['age']].value 
        vendor  = ''.join( ds[id_tags['vendor']].value  ).split ()  [0]
        model  = ''.join( ds[id_tags['model']].value  ).split ()  [0]
        kvp  = float( ds[geom_tags['kvp']].value  )
        diam  = float( ds[geom_tags['diam']].value  )
        rot_time  = float( ds[geom_tags['rot_time']].value  )
        #slice_spacing  = float( ds[geom_tags['slice_spacing']].value  )
        #slice_thickness  = float( ds[geom_tags['slice_thickness']].value  )
        rFOV  = float( ds[geom_tags['rFOV']].value  )
        table_speed  = float( ds[geom_tags['table_speed']].value  )
        pitch_mm  = float( ds[geom_tags['pitch_mm']].value  )

        pixel_size  =float( ( ds[geom_tags['pixel_size']].value  ) [0] )

        mAs  = float( ds[id_tags['mA']].value  )

        list1 =  [patname, sex, age,  model,  kvp, diam,  mAs,\
            rot_time, table_speed, pitch_mm, \
          total_files , rFOV, pixel_size ]
        
      else : 

        pitch_factor  = ds[geom_tags['pitch']].value 
        rows  = ds[geom_tags['rows']].value 
        cols  = ds[geom_tags['cols']].value 

        ffsmode = ds [private_acq_tags['ffsmode']].value.decode ('utf-8') 
        s2o = unpack_float (ds [private_acq_tags['s2o']].value )
        s2d = unpack_float (ds [private_acq_tags['s2d']].value )
        num_views_2pi = unpack_uint (   ds [private_acq_tags['num_angles_per_rotation']].value ) 

        center = unpack_array (ds [private_acq_tags['center_detector']].value )

        du = unpack_float ( ds [ private_det_tags ['det_spacing_du']].value )   
        dv = unpack_float( ds[private_det_tags ['det_spacing_dv']].value )  
        shape = ds [ private_det_tags  [ 'det_shape']] .value .decode () 

        srcz_first =   unpack_float (     ds [  private_src_tags ['src_z'] ].value  )  
        ds_last = dicom.dcmread (fnames [-1])
        srcz_last =   unpack_float (     ds_last [  private_src_tags ['src_z'] ].value  )  

        list2 =  [  pitch_factor, rows, cols, ffsmode, s2o, s2d, num_views_2pi, du, dv, shape,\
            srcz_first, srcz_last, srcz_last - srcz_first, total_files]

  new_row = list1 + list2
  df.loc [len (df)] = new_row

#print (df.iloc [:, : len (df.columns)//2])
print (df.iloc [:, : 15  ])

save_excel = False 
save_excel = True 

if save_excel  : 
#df.to_excel ('patient_abdomen_summary.xls')
  df.to_csv ('patient_abdomen_summary.csv')

#print (stop)



