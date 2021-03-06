#! /usr/bin/env python

# This script converts the fits files from the NIRCam CRYO runs at Lockheed
# into ssb-conform fits files.


# export UAZCONVDIR='/grp/jwst/wit/nircam/nircam-tools/pythonmodules/'
# export JWSTTOOLS_PYTHONMODULES='$JWSTTOOLS_ROOTDIR/pythonmodules'
# export JWSTTOOLS_ROOTDIR='/grp/jwst/wit/nircam/nircam-tools'
# export JWSTTOOLS_INSTRUMENT='NIRCAM'

import sys, os,re,math
import optparse,scipy
from astropy.io import fits as pyfits
from jwst import datamodels as models
from astropy.io import ascii
import numpy as np


# check subarray names in CRDS
subarrays = ascii.read("NIRCam_subarray_definitions.list")


sys.path.append(os.environ['UAZCONVDIR'])
from nircam2ssb import nircam2ssbclass

class sci2ssbclass(nircam2ssbclass):
    def __init__(self):
        nircam2ssbclass.__init__(self)

    def image2ssb(self,inputfilename, outfilebasename='auto',outdir=None,outsuffix=None,outsubdir=None):
        outfilebasename = self.mkoutfilebasename(inputfilename, outfilebasename=outfilebasename,outdir=outdir,outsuffix=outsuffix,outsubdir=outsubdir)
        (self.data,self.hdr)=pyfits.getdata(inputfilename, 0, header=True)
        print 'Input shape:',self.data.shape

        self.runID = self.getRunID(filename=inputfilename)
        self.hdr['SUBARRAY'] = 'FULL'

        # How many groups and integrations?
        if self.runID=='TUCSONNEW':
            Nint=1
        else:
            Nint = int(self.hdr['NINT'])
        Ngroup =int(self.hdr['NGROUP'])
        Nframe = int(self.hdr['NFRAME'])
        print 'NGROUP:',Ngroup
        print 'NINT:',Nint
        if (Ngroup*Nint)!=self.data.shape[0]:
            raise RuntimeError,'something is wrong! NGROUP=%d, NINT=%d, sum is not shape[0]=%d' % (Ngroup,Nint,self.data.shape[0])

        # rearrange the data: 4th coordinate is integration
        scinew=scipy.zeros((Nint,Ngroup,self.data.shape[1],self.data.shape[2]), dtype=float)
        for i in xrange(Nint):
            scinew[i,:,:,:]=self.data[i*Ngroup:(i+1)*Ngroup,:,:]
        print 'Output shape:',scinew.shape

        self.outputmodel = models.RampModel(data=scinew)

        #Mask dead pixels
        #mask = scipy.where(np.isnan(scinew))
        # mask = np.where(np.isnan(a))
        #mask = np.isnan(scinew)
        # a=scinew[mask]
        #print mask
        #sys.exit(0)

        #updates the date string
        self.updatemetadata(inputfilename,reffileflag=False)
        print('meta data updated')
        #update detector
        self.cryo_update_meta_detector(reffileflag=False)
        print('cryo meta data updated')
        #flip the data around to place it in the science orientation expected by SSB
        if self.runID in ['CV2','CV3', 'OTIS']:
            self.native_to_science_image_flip()

        if self.runID in ['CV3']:
            self.outputmodel.meta.exposure.readpatt = self.hdr['READOUT']

        if self.runID in ['OTIS']:
            self.outputmodel.meta.exposure.readpatt = self.hdr['READOUT']



        self.outputmodel.meta.exposure.nints = Nint
        self.outputmodel.meta.exposure.nframes = Nframe
        #self.outputmodel.meta.exposure.ngroups = self.hdr['NAXIS3']
        self.outputmodel.meta.exposure.ngroups = Ngroup

        # put the version of nircam2ssb into header
        # self.outputmodel.meta.channel = self.version

        outfilename = outfilebasename
        if not re.search('fits$',outfilename): outfilename += '_uncal.fits'

        print 'Saving %s' % outfilename
        self.outputmodel.save(outfilename)

        return(outfilename)


    def native_to_science_image_flip(self):
        #flip the data to match the orientation expected by SSB
        data = self.outputmodel.data
        print('trying to flip the image')
        if self.hdr['DETECTOR'] in ['NRCA2','NRCA4','NRCB1','NRCB3','NRCBLONG']:
            #vertical flip
            flip = data[:,:,::-1]
            self.outputmodel.data = flip
            self.outputmodel.meta.subarray.fastaxis = 1
            self.outputmodel.meta.subarray.slowaxis = -2
            try:
                detector_row_start = self.hdr['ROWSTART']
            except KeyError:
                print('Unable to get subarray ROWSTART, using 1')
                detector_row_start = '0.000000'
            try:
                detector_row_start = int(float(detector_row_start)) + 1
            except ValueError:
                print('Unable to convert ROWSTART to a valid integer, using 1')
                detector_row_start = 1
            try:
                detector_column_start = self.hdr['COLSTART']
            except KeyError:
                print('Unable to get subarray COLSTART, using 1')
                detector_column_start = '0.00000'
            try:
                detector_column_start = int(float(detector_column_start)) + 1
            except ValueError:
                print('Unable to convert COLSTART to a valid integer, using 1')
                detector_column_start = 1

            ncols = self.hdr['NAXIS1']
            nrows = self.hdr['NAXIS2']
            #
            # Since we're flipping these data in the Y-direction only, COLSTART and COLSTOP
            # will be unchanged.
            # ROWSTART and ROWSTOP will swap and subtract from 2049
            # FASTAXIS is 1, as the detector is still read from left to right
            colstart = detector_column_start
            colstop = colstart + ncols - 1
            rowstop = 2049 - detector_row_start
            rowstart = rowstop - nrows + 1
            fastaxis = 1
            slowaxis = -2

        elif self.hdr['DETECTOR'] in ['NRCA1','NRCA3','NRCB2','NRCB4','NRCALONG']:
            #horizontal flip
            flip = data[:,:,:,::-1]
            self.outputmodel.data = flip
            self.outputmodel.meta.subarray.fastaxis = -1
            self.outputmodel.meta.subarray.slowaxis = 2

            try:
                detector_row_start = self.hdr['ROWSTART']
            except KeyError:
                print('Unable to get subarray ROWSTART, using 1')
                detector_row_start = '0.000000'
            try:
                detector_row_start = int(float(detector_row_start)) + 1
            except ValueError:
                print('Unable to translate ROWSTART to a valid integer, using 1')
                detector_row_start = 1
            try:
                detector_column_start = self.hdr['COLSTART']
            except KeyError:
                print('Unable to get subarray COLSTART, using 1')
                detector_column_start = '0.00000'
            try:
                detector_column_start = int(float(detector_column_start)) + 1
            except ValueError:
                print('Unable to translate COLSTART to a valid integer, using 1')
                detector_column_start = 1

            ncols = self.hdr['NAXIS1']
            nrows = self.hdr['NAXIS2']
            #
            # Since we're flipping these data in the X-direction only, ROWSTART and ROWSTOP
            # will be unchanged.
            # COLSTART and COLSTOP will swap and subtract from 2049
            # FASTAXIS is -1, as the detector is now read from right to left
            rowstart = detector_row_start
            rowstop = rowstart + nrows - 1
            colstop = 2049 - detector_column_start
            colstart = colstop - ncols + 1
            fastaxis = -1
            slowaxis = 2
        else:
            print("WARNING! I don't recognize {} as a valid detector!".format(self.detector))
            sys.exit(0)

        self.hdr['DMSCOORD'] = 'JWST'
        self.hdr['COLSTART'] = colstart
        self.hdr['COLSTOP'] = colstop
        self.hdr['ROWSTART'] = rowstart
        self.hdr['ROWSTOP'] = rowstop
        self.hdr['NAXIS1'] = ncols
        self.hdr['NAXIS2'] = nrows
        self.hdr['FASTAXIS'] = fastaxis
        self.hdr['SLOWAXIS'] = slowaxis
        print('trying to get the subarray name')
        #  Update the subarray parameters
        subarray_name = self.get_subarray_name(subarrays, colstart-1, colstop-1, rowstart-1, rowstop-1)
        self.hdr['SUBARRAY'] = subarray_name
        print('subarray name is:',subarray_name)

if __name__=='__main__':

    usagestring='USAGE: sci3ssb.py infile1 infile2 ...'

    sci2ssb=sci2ssbclass()
    parser = sci2ssb.add_options(usage=usagestring)
    options,  args = parser.parse_args()

    if len(args)<1:
        parser.parse_args(['--help'])
        sys.exit(0)

    sci2ssb.verbose=options.verbose

    for infile in args:
        sci2ssb.image2ssb(infile,outfilebasename=options.outfilebasename,outdir=options.outdir,outsuffix=options.outsuffix,outsubdir=options.outsubdir)
