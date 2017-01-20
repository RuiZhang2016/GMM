# -*- coding: UTF-8 -*-

"""
Script to time different Univariate Gaussian inferences
"""

import os
import csv
import sys
import string
import subprocess

PATH = '../../tfInference/UnivariateGaussian/'

def main():

	with open('csv/ugm_times.csv', 'wb') as csvfile:

		writer = csv.writer(csvfile, delimiter=';')
		writer.writerow(['Inference type', 'Dataset size', 'Time', 'Iterations', 'ELBO'])

		inferences = ['coordAsc/ugm_cavi', 'gradAsc/ugm_gavi']
		nelements = [100, 500, 1000]
		iterations = 1

		for inference in inferences:
			for n in nelements:
				script = '{}{}.py'.format(PATH, inference)
				total_time = 0
				total_iters = 0
				total_elbos = 0
				for i in xrange(iterations):
					output = subprocess.check_output(['python', script, '-nElements', str(n), 
													 '--timing', '--getNIter', '--getELBO', '--no-debug'])
					time = float(((output.split('\n')[0]).split(': ')[1]).split(' ')[0])
					iters = int((output.split('\n')[1]).split(': ')[1])
					elbos = (((output.split('\n')[2]).split(': [')[1]).split(']')[0]).split(', ')
					elbos = [float(lb) for lb in elbos]
					total_time += time
					total_iters += iters
					total_elbos += elbos[-1]
				writer.writerow([inference, n, total_time/iterations, 
								 total_iters/iterations, total_elbos/iterations])

				with open('csv/ugm_{}_elbos_{}.csv'.format(inference.split('/')[1], n), 'wb') as csvfile:
					output = subprocess.check_output(['python', script, '-nElements', 
										  			  str(nelements[0]), '--getELBO', '--no-debug'])
					elbos = ((output.split(': [')[1]).split(']')[0]).split(', ')
					writer2 = csv.writer(csvfile, delimiter=';')
					writer2.writerow(['Iteration', 'ELBO'])
					for i, lb in enumerate(elbos):
						writer2.writerow([i, lb])
		

if __name__ == '__main__': main()