
import numpy as np
import random
from matplotlib import rc, cm
import os, sys
import h5py
import logging, time
import sys

from matplotlib import pyplot as plt

from simulations.libs.adaptive_sensing import qTracking as qtrack
from simulations.libs.adaptive_sensing import tracking_sequence as trackSeq

reload (qtrack)
reload (trackSeq)

# total simulation time
time_interval = 5000e-6
# time required for each Ramsey for spin init and read-out (everything but sensing)
overhead = 0e-6

N = 5 #this will be over-written automatically later, if fixN = False
# k-th sensing time is repeated for Mk = G +f*(K-k) times
G = 5
F = 3
# nr of protocol repetitions (for statistics)
nr_reps = 1

# T2*
T2 = 1e-6
#Read-out fidelities for spin 0 and spin 1
fid0 = 1.
fid1 = 1.

track = True

folder = 'C:/'
exp = qtrack.TimeSequenceQ(time_interval=100e-6, overhead=0, folder=folder, nr_spins=7)

for i in range(25):
	exp.ramsey (t = (2**(i-1))*1e-6, theta = np.pi/2., do_plot= True)