# -*- coding: UTF-8 -*-

"""
Incremental Principal Component Analysis
"""

import argparse
import csv
import pickle as pkl

import numpy as np
from sklearn.decomposition import IncrementalPCA

"""
Parameters:
    * input: Input path (CSV with ; delimiter)
    * output: Output path (PKL file)
    * c: PCA number of principal components

Execution:
    python ipca.py
        -input /home/alberto/Documentos/data/real/porto/porto_int50.csv
        -output /home/alberto/Documentos/data/real/porto/porto_pca.pkl
        -c 50
"""

parser = argparse.ArgumentParser(description='PCA')
parser.add_argument('-input', metavar='input', type=str, default='')
parser.add_argument('-output', metavar='output', type=str, default='')
parser.add_argument('-c', metavar='c', type=int, default=50)
args = parser.parse_args()

INPUT = args.input
OUTPUT = args.output
N_COMPONENTS = args.c


def format_track(track):
    """
    Format track from String to coordinates list
    :param track: Track as a string
    :return: Track as a Python list of coordinates
    """
    new_track = []
    for point in track.split('[[')[1].split(']]')[0].split('], ['):
        aux = [float(n) for n in point.split(', ')]
        new_track.append(aux[0])
        new_track.append(aux[1])
    return new_track


def main():
    try:
        if not('.csv' in INPUT or '.CSV' in INPUT): raise TypeError
        if not('.pkl' in OUTPUT or '.PKL' in OUTPUT): raise TypeError

        with open(INPUT, 'rb') as input:
            reader = csv.reader(input, delimiter=';')
            reader.next()
            n = 0
            xn = []
            for track in reader:
                print('Track {}'.format(n))
                track = format_track(track[0])
                xn.append(track)
                n += 1

            print('Doing IPCA...')
            pca = IncrementalPCA(n_components=N_COMPONENTS, batch_size=500)
            xn_new = pca.fit_transform(xn)

            with open(OUTPUT, 'w') as output:
                pkl.dump({'xn': np.array(xn_new)}, output)

    except IndexError:
        print('CSV input file doesn\'t have the correct structure!')
    except TypeError:
        print('Input must be a csv and output a pkl!')
    except IOError:
        print('File not found!')


if __name__ == '__main__': main()