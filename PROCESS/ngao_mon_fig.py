import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import pandas as pd
import warnings

warnings.filterwarnings('ignore')

# open ngao and GOADI
ngao=np.load('ngao_mon.npy')
goadi=np.load('goadi_mon.npy')
date=np.load('date_mon.npy')

nbday=len(date)
pcs=np.zeros([len(ngao),2])
pcs[:,0]=ngao
pcs[:,1]=goadi

# Plotting settings
font = {'family': 'Arial', 'weight': 'bold', 'size': 16}
plt.rc('font', **font)

def plot_and_save(pcs, index, label, filename):
    nul = np.zeros(nbday)
    pos = np.zeros(nbday)
    neg = np.zeros(nbday)
    pos[pcs[:, index] > 0] = 1
    neg[pcs[:, index] < 0] = 1

    fig, ax = plt.subplots(figsize=(22, 4))
    ax.plot(np.arange(nbday), pcs[:, index], 'k')
    ax.axhline(0, color='k')
    ax.fill_between(np.arange(nbday), nul, pos * pcs[:, index], color='y', alpha=0.6)
    ax.fill_between(np.arange(nbday), nul, neg * pcs[:, index], color='b', alpha=0.6)
    ax.set_xticks(np.arange(0, nbday, 12))
    ax.set_xticklabels(date[::12], rotation=70)
    ax.set_ylabel(label)
    #ax.grid()
    fig.tight_layout()
    plt.savefig(filename)
    plt.show()

# Plot and save data
plot_and_save(pcs, 0, 'NGAO index', 'NGAO_mon.png')
plot_and_save(pcs, 1, 'GOADI index', 'GOADI_mon.png')

