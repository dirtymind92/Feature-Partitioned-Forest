'''
attack_generator.py

Created by 

name: Federico Marcuzzi
e-mail: federico.marcuzzi@unive.it

date 20/02/2020
'''

import numpy as np

from itertools import combinations
from joblib import Parallel,delayed

from certificates import fast_lower_bound

'''
 FUNCTION -> : 'brute_force_rec' performs all possible perturbations of x given the combination of features.
  *INPUT  -> start : boolean variable that identifies the first iteration
  *INPUT  -> x : original istance
  *INPUT  -> f2t : list of pairs (feature,thresholds). Each features is associated with a list of thresholds
  *INPUT  -> list_attack : list of possible evading istances
  *INPUT  -> batch size : maximum batch size of evading instances
  *OUTPUT -> list_attack : list of possible evading istances
'''
def brute_force_rec(start,x,f2t,list_attack,batch_size):
	if len(f2t) == 0:
		list_attack[0].append(np.copy(x))

		# if the number of generated evading instances exceeds the batch size then yield.
		if len(list_attack[0]) >= batch_size:
			yield np.asarray(list_attack[0])
			list_attack[0] = []
	else:
		pos, ths = f2t[0]
		val = x[pos]

		for th in ths:
			# perturb instance with 'th' value.
			x[pos] = th
			yield from brute_force_rec(False,x,f2t[1:],list_attack,batch_size)

		# set original value.
		x[pos] = val
		yield from brute_force_rec(False,x,f2t[1:],list_attack,batch_size)

	# if the number of evadin instances has never exceeded the batch size and the algorithm is at the first iteration then yield.
	if start == True and len(list_attack[0]) != 0:
		yield np.asarray(list_attack[0])
		list_attack[0] = []

'''
 FUNCTION -> : 'brute_force_parallel' generates all attacks for instance 'x'.
  *INPUT  -> model : the model to be tested
  *INPUT  -> x : original instance
  *INPUT  -> y : instance labels
  *INPUT  -> threshold_sets : list of thresholds inside the forest for each tree
  *INPUT  -> i : the instance number
  *INPUT  -> k : attacker budget
  *INPUT  -> batch size : maximum batch size of evading instances
  *OUTPUT -> : 0/1. 0 indicates that at least one attack was found, 1 no attacks were found. 
'''
def brute_force_parallel(model,x,y,threshold_sets,i,k,batch_size):
	print('start istance: ',i,'       ', end="\r")
	n_feat = len(x)

	# generates all combinations of d, k features.
	for f2t in combinations(enumerate(threshold_sets),k):
		for evad_inst in brute_force_rec(True,x,f2t,[[]],batch_size):
			# process the batch and check correctness of predictions.
			predict = model.predict(evad_inst) * y
			if np.sum(predict) != len(predict):
				# if there is an attack it executes the early termination.
				return 0

	# no attacks found
	return 1

'''
 FUNCTION -> : 'brute_force' generates all attacks for instance 'x'. The function divides the instances of the dataset into 'n_th' threads and performs attacks in parallel.
  *INPUT  -> model : the model to be tested
  *INPUT  -> X : set of original instances
  *INPUT  -> Y : instances labels
  *INPUT  -> k : attacker budget
  *INPUT  -> n_th : number of threads
  *INPUT  -> verbose : parameter for printing information on the execution of threads (0 indicates no printing)
  *OUTPUT -> : accuracy under attack
'''
def brute_force(model,X,Y,k,n_th=1,verbose=0):
	n_ist, n_feat = np.shape(X)
	threshold_sets = [ set([np.max(X)+1]) for _ in range(n_feat) ]

	ist_byte = 8 * n_feat * n_th
	batch_size = (10**9) // ist_byte

	# creates a list of thresholds inside the forest for each feature.
	for tr in model:
		for f,t in zip(tr.tree_.feature,tr.tree_.threshold):
			if f >= 0:
				threshold_sets[f].add(t)

	predict = model.predict(X)
	# removes instances that are already classified incorrectly.
	idx_correct = np.where(predict==Y)[0]
	X = X[idx_correct]
	Y = Y[idx_correct]
	# removes with FLB instances for which there is no attack on k features that evades the model.
	idx_broken = fast_lower_bound(model,X,Y,k)[k]
	X = X[idx_broken]
	Y = Y[idx_broken]
	
	# attacks in parallel.
	print('num istances: %d num features: %d num b: %d' % (len(idx_broken),len(threshold_sets),k))
	attack = Parallel(n_jobs=n_th,batch_size=1, verbose=verbose)(delayed(brute_force_parallel)
																(model,x,y,threshold_sets,i,k,batch_size)
																for x,y,i in zip(X,Y,range(len(Y))) )

	# computes accuracy under attack.
	return np.round((len(idx_correct) - len(idx_broken) + np.sum(attack)) / n_ist, decimals=3)