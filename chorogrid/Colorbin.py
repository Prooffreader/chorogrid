#!/usr/bin/python
# Filename: Colorbin.py

class Colorbin(object):
    """ Instantiate with a list of quantities and colors, then retrieve 
        the following attributes:
        .colors_out : output list of colors, same length as quantities
        .fenceposts : divisions between bins
        .labels: one per color
        .fencepostlabels: one per fencepost
        .complements: list of colors, see set_complements, below
        
        attributes that can be changed:
        .proportional : if True, all bins have fenceposts same distance
                        apart (with default bin_min, bin_mid and bin_max)
                      : if False, all bins have (insofar as possible) the same
                        number of members
                      : note that this can break if not every quantity is 
                        unique
        .bin_min, .bin_max, .bin_mid
        .decimals : if None, no rounding; otherwise round to this number
        
        methods:
        .set_decimals(n): just what it sounds like
        .recalc(fenceposts=True): recalculate colors (and fenceposts, if True)
         based on attributes
        .calc_complements(cutoff [between 0 and 1], color_below, color_above):
            if the greyscale color is below the cutoff (i.e. darker),
            complement is assigned color_below, otherwise color_above.
    """
    def __init__(self, quantities, colors_in, proportional=True, decimals=None):
        self.quantities = quantities
        self.colors_in = colors_in 
        self.proportional = proportional
        self.bin_min = min(self.quantities)
        self.bin_max = max(self.quantities)
        self.bin_mid = (self.bin_min + self.bin_max) / 2
        self.decimals = None
        self.recalc()
        self.complements = None
    def _calc_fenceposts(self):
        if self.proportional:
            self.fenceposts = []
            step_1 = (self.bin_mid - self.bin_min) / len(self.colors_in) * 2
            step_2 = (self.bin_max - self.bin_mid) / len(self.colors_in) * 2
            for i in range(len(self.colors_in)+1):
                if i < len(self.colors_in)/2:
                    self.fenceposts.append(self.bin_min + i * step_1)
                elif i == len(self.colors_in)/2:
                    self.fenceposts.append(self.bin_mid)
                else:
                    self.fenceposts.append(self.bin_max - 
                                           (len(self.colors_in) - i) * step_2)
        else:
            quant_sorted = list(self.quantities[:])
            quant_sorted.sort()
            step = len(quant_sorted) / len(self.colors_in)
            self.fenceposts = []
            for i in range(len(self.colors_in)):
                self.fenceposts.append(quant_sorted[int(i*step)])
            self.fenceposts.append(quant_sorted[-1])
        if self.decimals is not None:
            self.fenceposts = [round(x, self.decimals) for x in self.fenceposts]
    def _calc_labels(self):
        self.labels = []
        self.fencepostlabels = []
        for n1, n2 in zip(self.fenceposts[:-1], self.fenceposts[1:]):
            self.labels.append('{}-{}'.format(n1, n2))
            self.fencepostlabels.append(str(n1))
        self.fencepostlabels.append(str(n2))
    def _calc_colors(self):
        self.colors_out = []
        self.bin_counts = [0] * len(self.colors_in)
        for qty in self.quantities:
            bin_ = 0
            for i in range(1, len(self.colors_in)):
                if qty >= self.fenceposts[i]:
                    bin_ = i
            self.colors_out.append(self.colors_in[bin_])
            self.bin_counts[bin_] += 1
            
    def set_decimals(self, decimals):
        self.decimals = decimals
        
    def recalc(self, fenceposts = True):
        if fenceposts:
            self._calc_fenceposts()
        self._calc_labels()
        self._calc_colors()
    def count_bins(self):
        print('count  label')
        print('=====  =====')
        for label, cnt in zip(self.labels, self.bin_counts):
            print('{:5d}  {}'.format(cnt, label))
            
    def calc_complements(self, cutoff, color_below, color_above):
        self.complements = []
        for color in self.colors_out:
            r, g, b = tuple(int(color[1:][i:i + 6 // 3], 16) 
                            for i in range(0, 6, 2))
            grey = (0.299 * r + 0.587 * g + 0.114* b) / 256
            if grey < cutoff:
                self.complements.append(color_below)
            else:
                self.complements.append(color_above)