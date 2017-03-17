# -*- coding: UTF-8 -*-

"""
Coordinate Ascent Variational Inference
process to approximate a mixture of gaussians
"""

import argparse
import pickle as pkl
from time import time

import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
from numpy.linalg import det, inv
from scipy.special import gammaln, multigammaln, psi

from sklearn.cluster import KMeans
from viz import create_cov_ellipse

parser = argparse.ArgumentParser(description='CAVI in mixture of gaussians')
parser.add_argument('-maxIter', metavar='maxIter', type=int, default=100)
parser.add_argument('-dataset', metavar='dataset', type=str,
                    default='../../data/k8/data_k8_1000.pkl')
parser.add_argument('-k', metavar='k', type=int, default=8)
parser.add_argument('--verbose', dest='verbose', action='store_true')
parser.add_argument('--no-verbose', dest='verbose', action='store_false')
parser.set_defaults(verbose=True)
parser.add_argument('--randomInit', dest='randomInit', action='store_true')
parser.add_argument('--no-randomInit', dest='randomInit', action='store_false')
parser.set_defaults(randomInit=False)
args = parser.parse_args()

MAX_ITERS = args.maxIter
K = args.k
VERBOSE = args.verbose
RANDOM_INIT = args.randomInit
THRESHOLD = 1e-10
PATH_IMAGE = 'img/'


def dirichlet_expectation(alpha, k):
    """
    Dirichlet expectation computation
    \Psi(\alpha_{k}) - \Psi(\sum_{i=1}^{K}(\alpha_{i}))
    """
    return psi(alpha[k] + np.finfo(np.float32).eps) - psi(np.sum(alpha))


def softmax(x):
    """
    Softmax computation
    e^{x} / sum_{i=1}^{K}(e^x_{i})
    """
    e_x = np.exp(x - np.max(x))
    return (e_x + np.finfo(np.float32).eps) / (
        e_x.sum(axis=0) + np.finfo(np.float32).eps)


def update_lambda_pi(lambda_pi, lambda_phi, alpha_o):
    """
    Update lambda_pi
    alpha_o + sum_{i=1}^{N}(E_{q_{z}} I(z_{n}=i))
    """
    for k in range(K):
        lambda_pi[k] = alpha_o[k] + np.sum(lambda_phi[:, k])
    return lambda_pi


def update_lambda_beta(lambda_beta, beta_o, Nks):
    """
    Updtate lambda_beta
    beta_o + Nk
    """
    for k in range(K):
        lambda_beta[k] = beta_o + Nks[k]
    return lambda_beta


def update_lambda_nu(lambda_nu, nu_o, Nks):
    """
    Update lambda_nu
    nu_o + Nk
    """
    for k in range(K):
        lambda_nu[k] = nu_o + Nks[k]
    return lambda_nu


def update_lambda_m(lambda_m, lambda_phi, lambda_beta, m_o, beta_o, xn, N):
    """
    Update lambda_m
    (m_o.T * beta_o + sum_{n=1}^{N}(E_{q_{z}} I(z_{n}=i)x_{n})) / lambda_beta
    """
    for k in range(K):
        aux = np.array([0., 0.])
        for n in range(N):
            aux += lambda_phi[n, k] * xn[n, :]
        lambda_m[k, :] = ((m_o.T * beta_o + aux) / lambda_beta[k]).T
    return lambda_m


def update_lambda_W(lambda_W, lambda_phi, lambda_beta,
                    lambda_m, W_o, beta_o, m_o, xn_xnt, K, N):
    """
    Update lambda_W
    W_o + m_o * m_o.T + sum_{n=1}^{N}(E_{q_{z}} I(z_{n}=i)x_{n}x_{n}.T)
    - lambda_beta * lambda_m * lambda_m.T
    """
    for k in range(K):
        aux = np.array([[0., 0.], [0., 0.]])
        for n in range(N):
            aux += lambda_phi[n, k] * xn_xnt[n]
        lambda_W[k, :, :] = W_o + np.outer(beta_o * m_o,
                                           m_o.T) + aux - np.outer(
            lambda_beta[k] * lambda_m[k, :], lambda_m[k, :].T)
    return lambda_W


def update_lambda_phi(lambda_phi, lambda_pi, lambda_m,
                      lambda_nu, lambda_W, lambda_beta, xn, N, K, D):
    """
    Update lambda_phi
    softmax[dirichlet_expectation(lambda_pi) +
            lambda_m * lambda_nu * lambda_W^{-1} * x_{n} -
            1/2 * lambda_nu * lambda_W^{-1} * x_{n} * x_{n}.T -
            1/2 * lambda_beta^{-1} -
            lambda_nu * lambda_m.T * lambda_W^{-1} * lambda_m +
            D/2 * log(2) +
            1/2 * sum_{i=1}^{D}(\Psi(lambda_nu/2 + (1-i)/2)) -
            1/2 log(|lambda_W|)]
    """
    for n in range(N):
        for k in range(K):
            lambda_phi[n, k] = dirichlet_expectation(lambda_pi, k)
            lambda_phi[n, k] += np.dot(lambda_m[k, :], np.dot(
                lambda_nu[k] * inv(lambda_W[k, :, :]), xn[n, :]))
            lambda_phi[n, k] -= np.trace(
                np.dot((1 / 2.) * lambda_nu[k] * inv(lambda_W[k, :, :]),
                       np.outer(xn[n, :], xn[n, :])))
            lambda_phi[n, k] -= (D / 2.) * (1 / lambda_beta[k])
            lambda_phi[n, k] -= (1. / 2.) * np.dot(
                np.dot(lambda_nu[k] * lambda_m[k, :].T, inv(lambda_W[k, :, :])),
                lambda_m[k, :])
            lambda_phi[n, k] += (D / 2.) * np.log(2.)
            lambda_phi[n, k] += (1 / 2.) * np.sum(
                psi([((lambda_nu[k] / 2.) + ((1 - i) / 2.)) for i in range(D)]))
            lambda_phi[n, k] -= (1 / 2.) * np.log(det(lambda_W[k, :, :]))
        lambda_phi[n, :] = softmax(lambda_phi[n, :])
    return lambda_phi


def NIW_sufficient_statistics(k, D, lambda_nu, lambda_W, lambda_m, lambda_beta):
    """
    Expectations Normal Inverse Wishart sufficient statistics computation
        E[\Sigma^{-1}\mu] = \nu * W^{-1} * m
        E[-1/2\Sigma^{-1}] = -1/2 * \nu * W^{-1}
        E[-1/2\mu.T\Sigma^{-1}\mu] = -D/2 * \beta^{-1} - \nu * m.T * W^{-1} * m
        E[-1/2log|\Sigma|] = D/2 * log(2) + 1/2 *
            sum_{i=1}^{D}(Psi(\nu/2 + (1-i)/2)) - 1/2 * log(|W|)
    """
    return np.array([
        np.dot(lambda_nu[k] * inv(lambda_W[k, :, :]), lambda_m[k, :]),
        (-1 / 2.) * lambda_nu[k] * inv(lambda_W[k, :, :]),
        (-D / 2.) * (1 / lambda_beta[k]) - (1 / 2.) * lambda_nu[k] * np.dot(
            np.dot(lambda_m[k, :].T, inv(lambda_W[k, :, :])), lambda_m[k, :]),
        (D / 2.) * np.log(2.) + (1 / 2.) * np.sum(
            psi([((lambda_nu[k] / 2.) + ((1 - i) / 2.)) for i in range(D)])) - (
            1 / 2.) * np.log(det(lambda_W[k, :, :]))
    ])


def elbo(lambda_phi, lambda_pi, lambda_m, lambda_W, lambda_beta, lambda_nu,
         alpha_o, nu_o, beta_o, m_o, W_o, xn, xn_xnt, N, D, Nks):
    """
    ELBO computation
    """
    elbop = -(((D * (N + 1)) / 2.) * K * np.log(2. * np.pi))
    elbop -= (K * nu_o * D * np.log(2.)) / 2.
    elbop -= K * multigammaln(nu_o / 2., D)
    elbop += (D / 2.) * K * np.log(np.absolute(beta_o))
    elbop += (nu_o / 2.) * K * np.log(det(W_o))
    elboq = -((D / 2.) * K * np.log(2. * np.pi))
    for k in range(K):
        aux1 = np.array([0., 0.])
        aux2 = np.array([[0., 0.], [0., 0.]])
        for n in range(N):
            aux1 += lambda_phi[n, k] * xn[n, :]
            aux2 += lambda_phi[n, k] * xn_xnt[n]
        elbop = elbop - gammaln(alpha_o[k]) + gammaln(np.sum(alpha_o))
        elbop += (alpha_o[k] - 1 + np.sum(
            lambda_phi[:, k])) * dirichlet_expectation(alpha_o, k)
        ss_niw = NIW_sufficient_statistics(k, D, lambda_nu,
                                           lambda_W, lambda_m, lambda_beta)
        elbop += np.dot((m_o.T * beta_o + aux1).T, ss_niw[0])
        elbop += np.trace(
            np.dot((W_o + np.outer(beta_o * m_o, m_o.T) + aux2).T, ss_niw[1]))
        elbop += (beta_o + Nks[k]) * ss_niw[2]
        elbop += (nu_o + D + 2. + Nks[k]) * ss_niw[3]
        elboq = elboq - gammaln(lambda_pi[k]) + gammaln(np.sum(lambda_pi))
        elboq += (lambda_pi[k] - 1 + np.sum(
            lambda_phi[:, k])) * dirichlet_expectation(lambda_pi, k)
        elboq += np.dot((lambda_m[k, :].T * lambda_beta[k]).T, ss_niw[0])
        elboq += np.trace(np.dot((lambda_W[k, :, :] + np.outer(
            lambda_beta[k] * lambda_m[k, :], lambda_m[k, :].T)).T, ss_niw[1]))
        elboq += lambda_beta[k] * ss_niw[2]
        elboq += (lambda_nu[k] + D + 2) * ss_niw[3]
        elboq -= ((lambda_nu[k] * D) / 2.) * np.log(2.)
        elboq -= multigammaln(lambda_nu[k] / 2., D)
        elboq += (D / 2.) * np.log(np.absolute(lambda_beta[k]))
        elboq += (lambda_nu[k] / 2.) * np.log(det(lambda_W[k, :, :]))
        elboq += np.dot(np.log(lambda_phi[:, k]).T, lambda_phi[:, k])
    return elbop - elboq


def plot_iteration(ax_spatial, circs, sctZ, lambda_m,
                   lambda_W, lambda_nu, xn, D, i):
    """
    Plot the Gaussians in every iteration
    """
    if i == 0:
        plt.scatter(xn[:, 0], xn[:, 1], cmap=cm.gist_rainbow, s=5)
        sctZ = plt.scatter(lambda_m[:, 0], lambda_m[:, 1],
                           color='black', s=5)
    else:
        for circ in circs: circ.remove()
        circs = []
        for k in range(K):
            cov = lambda_W[k, :, :] / (lambda_nu[k] - D - 1)
            circ = create_cov_ellipse(cov, lambda_m[k, :], color='r',
                                      alpha=0.3)
            circs.append(circ)
            ax_spatial.add_artist(circ)
        sctZ.set_offsets(lambda_m)
    plt.draw()
    plt.pause(0.001)
    return ax_spatial, circs, sctZ


def init_kmeans(xn, N, K):
    """
    Init points assignations (lambda_phi) with Kmeans clustering
    """
    lambda_phi = 0.1 / (K - 1) * np.ones((N, K))
    labels = KMeans(K).fit(xn).predict(xn)
    for i, lab in enumerate(labels):
        lambda_phi[i, lab] = 0.9
    return lambda_phi


def main():
    # Get data
    with open('{}'.format(args.dataset), 'r') as inputfile:
        data = pkl.load(inputfile)
        xn = data['xn']
    N, D = xn.shape

    if VERBOSE:
        init_time = time()

    # Priors
    alpha_o = np.array([1.0] * K)
    nu_o = np.array([3.0])
    W_o = np.array([[20., 30.], [25., 40.]])
    m_o = np.array([0.0, 0.0])
    beta_o = np.array([0.7])

    # Variational parameters
    lambda_phi = np.random.dirichlet(alpha_o, N) if RANDOM_INIT \
        else init_kmeans(xn, N, K)
    lambda_pi = np.zeros(shape=K)
    lambda_beta = np.zeros(shape=K)
    lambda_nu = np.zeros(shape=K)
    lambda_m = np.zeros(shape=(K, D))
    lambda_W = np.zeros(shape=(K, D, D))

    xn_xnt = [np.outer(xn[n, :], xn[n, :].T) for n in range(N)]

    # Plot configs
    if VERBOSE:
        plt.ion()
        fig = plt.figure(figsize=(10, 10))
        ax_spatial = fig.add_subplot(1, 1, 1)
        circs = []
        sctZ = None

    # Inference
    lbs = []
    n_iters = 0
    for i in range(MAX_ITERS):

        # Variational parameter updates
        lambda_pi = update_lambda_pi(lambda_pi, lambda_phi, alpha_o)
        Nks = np.sum(lambda_phi, axis=0)
        lambda_beta = update_lambda_beta(lambda_beta, beta_o, Nks)
        lambda_nu = update_lambda_nu(lambda_nu, nu_o, Nks)
        lambda_m = update_lambda_m(lambda_m, lambda_phi, lambda_beta, m_o,
                                   beta_o, xn, N)
        lambda_W = update_lambda_W(lambda_W, lambda_phi, lambda_beta, lambda_m,
                                   W_o, beta_o, m_o, xn_xnt, K, N)
        lambda_phi = update_lambda_phi(lambda_phi, lambda_pi, lambda_m,
                                       lambda_nu, lambda_W, lambda_beta, xn, N,
                                       K, D)

        # ELBO computation
        lb = elbo(lambda_phi, lambda_pi, lambda_m, lambda_W, lambda_beta,
                  lambda_nu, alpha_o, nu_o, beta_o, m_o, W_o, xn, xn_xnt, N, D,
                  Nks)
        lbs.append(lb)
        n_iters += 1

        if VERBOSE:
            print('\n******* ITERATION {} *******'.format(i))
            print('lambda_pi: {}'.format(lambda_pi))
            print('lambda_beta: {}'.format(lambda_beta))
            print('lambda_nu: {}'.format(lambda_nu))
            print('lambda_m: {}'.format(lambda_m))
            print('lambda_W: {}'.format(lambda_W))
            print('lambda_phi: {}'.format(lambda_phi[0:9, :]))
            print('ELBO: {}'.format(lb))
            ax_spatial, circs, sctZ = plot_iteration(ax_spatial, circs, sctZ,
                                                     lambda_m, lambda_W,
                                                     lambda_nu, xn, D, i)

        # Break condition
        if i > 0 and abs(lb - lbs[i - 1]) < THRESHOLD:
            plt.savefig('{}/results.png'.format(PATH_IMAGE))
            break

    if VERBOSE:
        print('\n******* RESULTS *******')
        for k in range(K):
            print('Mu k{}: {}'.format(k, lambda_m[k, :]))
            print('SD k{}: {}'.format(k, np.sqrt(
                lambda_W[k, :, :] / (lambda_nu[k] - D - 1))))
        final_time = time()
        exec_time = final_time - init_time
        print('Time: {} seconds'.format(exec_time))
        print('Iterations: {}'.format(n_iters))
        print('ELBOs: {}'.format(lbs))


if __name__ == '__main__': main()
