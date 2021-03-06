# -*- coding: UTF-8 -*-

"""
Dimensionality reduction with an autoencoder
"""

import argparse
import csv
import pickle as pkl
import sys

import numpy as np
from keras.layers import Dense, Input
from keras.models import Model

from .common import format_track

"""
Parameters:
    * input: Input path (CSV with ; delimiter)
    * output: Output path (PKL file)
    * c: Number of components

Execution:
    python ae.py -input mallorca_nnint50.csv 
                 -output generated/mallorca_nnint50_ae50.pkl -c 50
"""

parser = argparse.ArgumentParser(description='Autoencoder')
parser.add_argument('-input', metavar='input', type=str, default='')
parser.add_argument('-output', metavar='output', type=str, default='')
parser.add_argument('-c', metavar='c', type=int, default=50)
args = parser.parse_args()

N_EPOCHS = 300


def main():
    try:
        if not ('.csv' in args.input): raise Exception('input_format')
        if not ('.pkl' in args.output): raise Exception('output_format')

        with open(args.input, 'rb') as input:
            reader = csv.reader(input, delimiter=';')
            reader.next()
            n = 0
            xn = []
            for track in reader:
                print('Track {}'.format(n))
                track = format_track(track[0])
                xn.append(track)
                n += 1
            xn = np.array(xn).astype('float32') / np.max(xn)

            print('Doing autoencoder...')

            # Autoencoder definition
            input_track = Input(shape=(len(xn[0]),))

            encoded = Dense(args.c * 2, activation='tanh')(input_track)
            encoded = Dense(args.c, activation='tanh')(encoded)

            decoded = Dense(args.c * 2, activation='tanh')(encoded)
            decoded = Dense(len(xn[0]), activation='sigmoid')(decoded)

            ae = Model(input_track, decoded)

            # Encoder definition
            encoder = Model(input_track, encoded)

            # Train autoencoder
            ae.compile(optimizer='adadelta', loss='binary_crossentropy')
            ae.fit(xn, xn, epochs=N_EPOCHS, batch_size=256, shuffle=True)

            # Get points compressed representations
            xn_new = encoder.predict(xn)

            # Normalization
            maxs = np.max(xn_new, axis=0)
            mins = np.min(xn_new, axis=0)
            rng = maxs - mins
            high = 100.0
            low = 0.0
            xn_new = high - (((high - low) * (maxs - xn_new)) / rng)

            with open(args.output, 'w') as output:
                pkl.dump({'xn': np.array(xn_new)}, output)

    except IOError:
        print('File not found!')
    except Exception as e:
        if e.args[0] == 'input_format':
            print('Input must be a CSV file')
        elif e.args[0] == 'output_format':
            print('Output must be a PKL file')
        else:
            print('Unexpected error: {}'.format(sys.exc_info()[0]))
            raise


if __name__ == '__main__': main()
