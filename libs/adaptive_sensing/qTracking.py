import numpy as np
import random
from matplotlib import rc, cm
import matplotlib
import os, sys
import h5py
import cmath
import logging, time, timeit
from importlib import reload

#sys.path.append ('/Users/dalescerri/Documents/GitHub')

import matplotlib.pyplot as plt
from scipy import signal
from simulations.libs.math import statistics as stat
from simulations.libs.adaptive_sensing import adaptive_tracking as adptvTrack
from simulations.libs.spin import diluted_NSpin_bath_py3_dale as NSpin

reload (NSpin)
reload (adptvTrack)
reload (stat)

matplotlib.rc('xtick', labelsize=18) 
matplotlib.rc('ytick', labelsize=18)


class TimeSequenceQ (adptvTrack.TimeSequence_overhead):

	def __init__ (self, time_interval, overhead, folder):
		self.time_interval = time_interval
		self._B_dict = {}
		self.kappa = None
		self.curr_fB_idx = 0
		self.OH = overhead
		self.set_fB = []
		self.est_fB = []
		self.curr_fB = 0
		self.plot_idx = 0
		#self.step=0

		# The "called modules" is  a list that tracks which functions have been used
		# so that they are saved in the output hdf5 file.
		# When you look back into old data, it's nice to have some code recorded
		# to make sure you know how the data was generated (especially if you tried out diffeent things)
		self._called_modules = ['ramsey', 'bayesian_update', 'calc_acc_phase']
		self.folder = folder

	def set_spin_bath (self, nr_spins, concentration, verbose = False, do_plot = False):
		
		# Spin bath initialization
		self.nbath = NSpin.SpinExp_cluster1()
		self.nbath.set_experiment(nr_spins=nr_spins, concentration = concentration,
				do_plot = do_plot)
		self.T2star = self.nbath.T2l*1e-6
		print ("T2* at low magnetic field: ", int(self.T2star*1e10)/10)

		if verbose:
			self.nbath.print_nuclear_spins()

	def init_a_priory (self):
		pass

	def initialize (self):
		# B_std = 1/(sqrt(2)*pi*T2_star)
		self._dfB0 = 1./(4.442883*self.T2star)
		print ("std fB: ", self._dfB0*1e-3, " kHz")

		p = np.exp(-0.5*(self.beta/self._dfB0)**2)
		p = p/(np.sum(p))
		self.p_k = np.fft.ifftshift(np.abs(np.fft.ifft(p, self.discr_steps))**2)
		self.renorm_p_k()

		self.plot_hyperfine_distr()


	def plot_hyperfine_distr(self):
		p, m = self.return_p_fB()
		#h, az = self.nbath.get_histogram_Az(nbins = 100)
		az, p_az = self.nbath.get_probability_density()
		plt.figure(figsize = (12,6))
		plt.plot (az, p_az/np.sum(p_az), 'o', color='royalblue', label = 'spin-bath')
		plt.xlabel (' hyperfine (kHz)', fontsize=18)
		plt.plot (self.beta*1e-3, p, '--', color='crimson', linewidth = 2, label = 'classical')
		plt.xlabel (' hyperfine (kHz)', fontsize=18)
		plt.legend()
		#plt.savefig('%.04d'%self.step)
		plt.show()
		#self.step+=1


	def return_std (self, verbose=False):

		'''
		Returns:
		std_H 		standard deviation for the frequency f_B (calculated from p_{-1}). SOmetimes returns negative Holevo
		fom 		figure of merit	
		'''

		self.renorm_p_k()
		print ("|p_(-1)| = ", np.abs(self.p_k[self.points-1]))
		Hvar = (2*np.pi*np.abs(self.p_k[self.points-1]))**(-2)-1
		print('Hvar',Hvar)
		std_H = ((abs(cmath.sqrt(Hvar)))/(2*np.pi*self.tau0))
		#fom = self.figure_of_merit()
		if verbose:
			print ("Std (Holevo): ", std_H*1e-3 , ' kHz')
		return  std_H, 0

	def reset_called_modules(self):
		self._called_modules = ['ramsey', 'bayesian_update', 'calc_acc_phase']

	def ramsey (self, t=0., theta=0., do_plot = False):

		'''
		Ramsey experiment simulation
		Calculates the probabilities p0 and p1 to get 0/1 and draws an outcome with the probabilities

		Input:
		t 		[ns]		sensing time
		theta	[rad]		Ramsey phase

		Returns:
		Ramsey outcome
		'''

		az0, pd0 = np.real(self.nbath.get_probability_density())
		m = self.nbath.Ramsey (tau=t, phi = theta)
		az, pd = np.real(self.nbath.get_probability_density())

		if do_plot:
			self.plot_hyperfine_distr()
			
			#title = 'Ramsey: tau = '+str(int(t*1e9))+' ns -- phase: '+str(int(theta*180/3.14))+' deg'
			#plt.figure (figsize = (8,4))
			#plt.plot (az0, pd0, linewidth=2, color = 'RoyalBlue')
			#plt.plot (az, pd, linewidth=2, color = 'crimson')
			#plt.xlabel ('frequency hyperfine (kHz)', fontsize=18)
			#plt.ylabel ('probability', fontsize=18)
			#plt.title (title, fontsize=18)
			#plt.show()

		return m

	def find_optimal_k (self, do_debug=False):
		width, fom = self.return_std (verbose=True)
		print('optk+1',np.log(1/(width*self.tau0))/np.log(2))
		print('width',width)
		opt_k = np.int(np.log(1/(width*self.tau0))/np.log(2))-1
        
		#TEMPORARY fix for when opt_k is negative. In case flag is raised, best to reset simulation for now
		if opt_k<0:
			print('K IS NEGATIVE',opt_k)
			opt_k = 0
		if do_debug:
			print ("Optimal k = ", opt_k)
		return opt_k

	def adptv_tracking_single_step (self, k, M, do_debug=False):

		t_i = int(2**k)
		ttt = -2**(k+1)
		t0 = self.running_time					

		#print ("idx_capp = ", ttt+self.points)

		phase_cappellaro = 0.5*np.angle (self.p_k[int(ttt+self.points)])
		print('Phase',phase_cappellaro)
		m_list = []
		print('Ramsey time', t_i*self.tau0)
		print('tau_0 time', self.tau0)
		for m in range(M):
			m_res = self.ramsey (theta=phase_cappellaro, t = t_i*self.tau0, do_plot=do_debug)
			m_list.append(m_res)	
			self.bayesian_update (m_n = m_res, phase_n = phase_cappellaro, t_n = t_i, do_plot=False)
			if do_debug:
				print ("Estimation step: t_units=", t_i, "    -- res:", m_res)

		return m_list


	def qTracking (self, M=1, do_plot = False, do_debug=False):

		'''
		Simulates adaptive tracking protocol

		Input: do_plot [bool], do_debug [bool]
		'''

		self._called_modules.append('adaptive_tracking_estimation')
		self.running_time = 0

		for i in range(100):
			opt_k = self.find_optimal_k (do_debug = do_debug)
			m_list = self.adptv_tracking_single_step (k = opt_k, M=M, do_debug = do_debug)

	def simulate(self, track, do_save = False, do_plot = False, kappa = None, do_debug=False):
		self.k_array = self.K-np.arange(self.K+1)
		self.init_apriori ()

		total_units = 0
		self.curr_step = -1

		self.prev_estim = 0
		self.total_time = np.array([])

		self.running_time = 0
		self.nr_estimations = 0

		while (self.running_time < self.time_interval):
			if not(track):
				self.init_apriori ()

			self.curr_step = self.curr_step + 1

			if track:
				self.adaptive_tracking_estimation(do_plot=do_plot, do_debug=do_debug)
			else:
				self.non_tracking_estimation (do_plot=do_plot)
		self.nr_time_steps = self.curr_step

