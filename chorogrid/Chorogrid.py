#!/usr/bin/python
# Filename: Chorogrid.py

import xml.etree.ElementTree as ET
import pandas as pd
import re
import sys
from math import sqrt
from IPython.display import SVG, display

class Chorogrid(object):
    """ An object which makes choropleth grids, instantiated with:
            csv_path: the path to a csv data file with the following columns:
                * ids: e.g., states or countries, corresponding to
                       the Colorbin.colorlist
                * coordinates or path
            ids: a listlike object of ids corresponding to colors
            colors: a listlike object of colors in hex (#123456) format
                    corresponding to ids
            id_column: the name of the column in csv_path containing ids
                       if there is not a 1:1 map between the ids object
                       and the contents of id_column, you will be warned
            
        Methods (introspect to see arguments)
           set_colors: pass a new list of colors to replace the one
                       used when the class was instantiated
           set_title: set a title for the map
           set_legend: set a legend
           add_svg: add some custom svg code. This must be called
                      after the draw_... method, because it needs to know
                      the margins.
           
           draw_squares: draw a square grid choropleth
           draw_hex: draw a hex-based choropleth
           draw_multihex: draw a multiple-hex-based choropleth
           draw_multisquare: draw a multiple-square-based choropleth
           draw_map: draw a regular, geographic choropleth
           
           done: save and/or display the result in IPython notebook
           done_with_overlay: overlay two Chorogrid objects
    """
    def __init__(self, csv_path, ids, colors, id_column='abbrev'):
        self.df = pd.read_csv(csv_path)
        comparison_set = set(self.df[id_column])
        invalid = set(ids).difference(comparison_set)
        missing = comparison_set.difference(set(ids))
        if len(invalid) > 0:
            print('WARNING: The following are not recognized'
                  ' ids: {}'.format(invalid), file=sys.stderr)
        if len(missing) > 0:
            print('WARNING: The following ids in the csv are not '
                  'included: {}'.format(missing), file=sys.stderr)
        self.colors = list(colors)
        self.ids = list(ids)
        self.svglist = []
        assert id_column in self.df.columns, ("{} is not a column in"
            " {}".format(id_column, csv_path))
        self.id_column = id_column
        self.title = ''
        self.additional_svg = []
        self.additional_offset = [0, 0]
        self.legend_params = None

    #methods called from within methods, beginning with underscore
    def _update_default_dict(self, default_dict, dict_name, kwargs):
        """Updates a dict based on kwargs"""
        if dict_name in kwargs.keys():
            kwarg_dict = kwargs[dict_name]
            for k, v in kwarg_dict.items():
                assert k in default_dict.keys(), ("kwarg {} specified invalid"
                    " key".format(dict_name))
                if k == 'font-size' and type(k) is int:
                    default_dict[k] = str(v) + 'px'
                else:
                    default_dict[k] = v
        return default_dict
    def _dict2style(self, dict_):
        """Returns a concatenated string from the dict"""
        to_return = []
        for k,v in dict_.items():
            to_return.append(k + ':' + str(v) + ';')
        to_return[-1] = to_return[-1][:-1]
        return ''.join(to_return)
    def _make_svg_top(self, width, height):
        """Writes first part of svg"""
        self.svg = ET.Element('svg', xmlns="http://www.w3.org/2000/svg", 
            version="1.1", height=str(height), width=str(width))
    def _draw_title(self, x, y):
        if len(self.title) > 0:
            font_style = self._dict2style(self.title_font_dict)
            _ = ET.SubElement(self.svg, "text", id="title", x=str(x), 
                              y=str(y), style=font_style)
            _.text = self.title
    def _determine_font_colors(self, kwargs):
        if 'font_colors' in kwargs.keys():
            fc = kwargs['font_colors']
            if type(fc) is str:
                font_colors = [fc] * len(self.ids)
            elif type(fc) is list:
                font_colors = fc
            elif type(fc) is dict:
                font_colors = [fc[x] for x in self.colors]
        else:
            font_colors = ['#000000'] * len(self.ids)
        return font_colors
    def _calc_hexagon(self, x, y, w, true_rows):
        if true_rows:
            h = w/sqrt(3)
            return "{},{} {},{} {},{} {},{} {},{} {},{}".format(x, y,
                                                                x+w/2, y-h/2,
                                                                x+w, y,
                                                                x+w, y+h,
                                                                x+w/2, y+1.5*h,
                                                                x, y+h)
        else:
            ww = w/2
            hh = w * sqrt(3) / 2
            return "{},{} {},{} {},{} {},{} {},{} {},{}".format(x, y,
                                                                x+ww, y,
                                                                x+ww*3/2, y-hh/2,
                                                                x+ww, y-hh,
                                                                x, y-hh,
                                                                x-ww/2, y-hh/2)
            
    def _increment_multihex(self, x, y, w, direction):                                        
        h = w/sqrt(3)
        if direction == 'a':
            return 'L', x+w/2, y-h/2
        elif direction == 'b':
            return 'L', x+w/2, y+h/2
        elif direction == 'c':
            return 'L', x, y+h
        elif direction == 'd':
            return 'L', x-w/2, y+h/2
        elif direction == 'e':
            return 'L', x-w/2, y-h/2
        elif direction == 'f':
            return 'L', x, y-h
        elif direction == 'A':
            return 'M', x+w/2, y-h/2
        elif direction == 'B':
            return 'M', x+w/2, y+h/2
        elif direction == 'C':
            return 'M', x, y+h
        elif direction == 'D':
            return 'M', x-w/2, y+h/2
        elif direction == 'E':
            return 'M', x-w/2, y-h/2
        elif direction == 'F':
            return 'M', x, y-h
    def _calc_multihex(self, x, y, w, contour):
        result = []
        result.append("M{}, {}".format(x, y))
        for letter in contour:
            LM, x, y = self._increment_multihex(x, y, w, letter)
            result.append("{}{}, {}".format(LM, x, y))
        result.append('Z')
        return " ".join(result)

    def _increment_multisquare(self, x, y, w, direction):                                        
        if direction == 'a':
            return 'L', x+w, y
        elif direction == 'b':
            return 'L', x, y+w
        elif direction == 'c':
            return 'L', x-w, y
        elif direction == 'd':
            return 'L', x, y-w
        elif direction == 'A':
            return 'M', x+w, y
        elif direction == 'B':
            return 'M', x, y-w
        elif direction == 'C':
            return 'M', x-w, y
        elif direction == 'D':
            return 'M', x, y+w
    def _calc_multisquare(self, x, y, w, contour):
        result = []
        result.append("M{}, {}".format(x, y))
        for letter in contour:
            LM, x, y = self._increment_multisquare(x, y, w, letter)
            result.append("{}{} {}".format(LM, x, y))
        result.append('Z')
        return " ".join(result)

    # functions to set properties that will be retained across different
    # types of grid
    def set_colors(self, colors):
        """change colors list specified when Chorogrid is instantiated"""
        self.colors = colors
        assert len(ids) == len(colors), ("ids and colors must be "
                                         "the same length")
    def set_title(self, title, **kwargs):
        """Set a title for the grid
           kwargs:
                font_dict
                default = {'font-style': 'normal', 'font-weight': 'normal', 
                      'font-size': '21px', 'line-height': '125%', 
                      'text-anchor': 'middle', 'font-family': 'sans-serif', 
                      'letter-spacing': '0px', 'word-spacing': '0px', 
                      'fill-opacity': 1, 'stroke': 'none', 
                      'stroke-width': '1px', 'stroke-linecap': 'butt', 
                      'stroke-linejoin': 'miter', 'stroke-opacity': 1,
                      'fill': '#000000'}"""
        self.title_font_dict = {'font-style': 'normal', 
                                'font-weight': 'normal', 
                                'font-size': '21px', 
                                'line-height': '125%', 
                                'text-anchor': 'middle', 
                                'font-family': 'sans-serif', 
                                'letter-spacing': '0px', 
                                'word-spacing': '0px', 
                                'fill-opacity': 1, 
                                'stroke': 'none', 
                                'stroke-width': '1px', 
                                'stroke-linecap': 'butt', 
                                'stroke-linejoin': 'miter', 
                                'stroke-opacity': 1,
                                'fill': '#000000'}
        self.title_font_dict = self._update_default_dict(
                               self.title_font_dict, 'font_dict', kwargs)
        self.title = title

    def set_legend(self, colors, labels, title=None, width="square", 
                   height=100, gutter=2, stroke_width=0.5, label_x_offset=2,
                   label_y_offset = 3, stroke_color="#303030", **kwargs):
        """Creates a legend that will be included in any draw method.
        * width can be the text "square" or a number of pixels.
        * a gradient can be made with a large number of colors, and ''
          for each label that is not specified, and non-square width
        * height does not include title
        * if len(labels) can be len(colors) or len(colors)+1; the labels
          will be aside the boxes, or at the interstices/fenceposts, 
          respectively; alternately, if len(labels) == 2, two fenceposts
          will be assigned
        
        kwarg: font_dict
            default: {'font-style': 'normal', 'font-weight': 'normal', 
                      'font-size': '12px', 'line-height': '125%', 
                      'text-anchor': 'left', 'font-family': 'sans-serif', 
                      'letter-spacing': '0px', 'word-spacing': '0px', 
                      'fill-opacity': 1, 'stroke': 'none', 
                      'stroke-width': '1px', 'stroke-linecap': 'butt', 
                      'stroke-linejoin': 'miter', 'stroke-opacity': 1,
                      'fill': '#000000'}
        """
        font_dict = {'font-style': 'normal', 
                     'font-weight': 'normal', 
                     'font-size': '12px', 
                     'line-height': '125%', 
                     'text-anchor': 'left', 
                     'font-family': 'sans-serif', 
                     'letter-spacing': '0px', 
                     'word-spacing': '0px', 
                     'fill-opacity': 1, 
                     'stroke': 'none', 
                     'stroke-width': '1px', 
                     'stroke-linecap': 'butt', 
                     'stroke-linejoin': 'miter', 
                     'stroke-opacity': 1}
        self.legend_height = height
        colors = colors[::-1]
        labels = labels[::-1]
        num_boxes = len(colors)
        if len(labels) == 2 and len(colors) > 2:
            _ = []
            _.append(labels[0])
            for i in range(num_boxes-1):
                _.append('')
            _.append(labels[1])
            labels = _
        height_n = len(labels)
        if title is not None and len(title)>0:
            height_n += 1
        box_height = ((height - gutter) / height_n ) - gutter
        if width == "square":
            width = box_height
        assert len(labels) - len(colors) <= 1, ("Length of labels must be"
            "two, or equal to colors or one more than colors")
        box_offset = (len(labels) - len(colors)) * (box_height + gutter) / 2
        font_style = self._dict2style(font_dict)
        if title is not None and len(title) > 0:
            y_offset = (int(font_dict['font-size'].replace('px', '')) + 
                        gutter * 0.75) # ugly tweak
        else:
            y_offset = 0
        # create a dict of legend parameters because these need to be defined BEFORE
        # the draw_ method creates the lxml SubElements.
        self.legend_params = {
            'colors': colors,
            'stroke_width': stroke_width,
            'stroke_color': stroke_color,
            'y_offset': y_offset,
            'box_height': box_height,
            'gutter': gutter,
            'width': width,
            'font_style': font_style,
            'label_x_offset': label_x_offset,
            'label_y_offset': label_y_offset,
            'labels': labels,
            'title': title}
    
    # another function-from-within, I'm placing it here to be right below the set_legend method
    def _apply_legend(self):
        d = self.legend_params # convenient one-letter-long dict name    
        for i, color in enumerate(d['colors']):
            style_text = ("fill:{0};stroke-width:{1}px;stroke:{2};fill-rule:"
                          "evenodd;stroke-linecap:butt;stroke-linejoin:miter;"
                          "stroke-opacity:1".format(color,
                              d['stroke_width'],
                              d['stroke_color']))
            ET.SubElement(self.legendsvg,
                          "rect", 
                          id="legendbox{}".format(i), 
                          x="0",
                          y=str(d['y_offset'] + i * (d['box_height'] + 
                          d['gutter'])), 
                          height=str(d['box_height']),
                          width=str(d['width']), 
                          style=style_text)
        for i, label in enumerate(d['labels']):
            style_text = d['font_style'] + ";alignment-baseline:middle"       
            _ = ET.SubElement(self.legendsvg, "text", id="legendlabel{}".format(
                    i), x=str(d['label_x_offset'] + d['width'] + d['gutter']),
                    y=str(d['label_y_offset'] + d['y_offset'] + i * (
                    d['box_height'] + d['gutter']) + 
                    (d['box_height']) / 2), style=style_text)
            _.text = label
        if d['title'] is not None and len(d['title']) > 0:   
            _ = ET.SubElement(self.legendsvg, "text", id="legendtitle", x="0", 
                              y="0", style=d['font_style'])
            _.text = d['title']

    def add_svg(self, text, offset=[0, 0]):
        """Adds svg text to the final output. Can be called more than once."""
        offset[0] += self.additional_offset[0]
        offset[1] += self.additional_offset[1]
        translate_text = "translate({} {})".format(offset[0], offset[1])
        text = ("<g transform=\"{}\">".format(translate_text) +
                text + "</g>")
        self.additional_svg.append(text)
        
    def done_and_overlay(self, other_chorogrid, show=True, save_filename=None):
        """Overlays a second chorogrid object on top of the root object."""
        svgstring = ET.tostring(self.svg).decode('utf-8')
        svgstring = svgstring.replace('</svg>', ''.join(self.additional_svg) + '</svg>')
        svgstring = svgstring.replace(">", ">\n")
        svgstring = svgstring.replace("</svg>", "")
        svgstring_overlaid = ET.tostring(other_chorogrid.svg).decode('utf-8')
        svgstring_overlaid = svgstring_overlaid.replace('</svg>', 
                                 ''.join(other_chorogrid.additional_svg) + '</svg>')
        svgstring_overlaid = svgstring_overlaid.replace(">", ">\n")
        svgstring_overlaid = re.sub('<svg.+?>', '', svgstring_overlaid)
        svgstring += svgstring_overlaid
        if save_filename is not None:
            if save_filename[-4:] != '.svg':
                save_filename += '.svg'
            with open(save_filename, 'w+', encoding='utf-8') as f:
                f.write(svgstring)
        if show:
            display(SVG(svgstring))
            
    # the .done() method           
    def done(self, show=True, save_filename=None):
        """if show == True, displays the svg in IPython notebook. If save_filename
           is specified, saves svg file"""
        svgstring = ET.tostring(self.svg).decode('utf-8')
        svgstring = svgstring.replace('</svg>', ''.join(self.additional_svg) + '</svg>')
        svgstring = svgstring.replace(">", ">\n")
        if save_filename is not None:
            if save_filename[-4:] != '.svg':
                save_filename += '.svg'
            with open(save_filename, 'w+', encoding='utf-8') as f:
                f.write(svgstring)
        if show:
            display(SVG(svgstring))
   
    # the methods to draw square grids, map (traditional choropleth),
    # hex grid, four-hex grid, multi-square grid
    
    def draw_squares(self, x_column='square_x', 
                     y_column='square_y', **kwargs):
        """ Creates an SVG file based on a square grid, with coordinates from 
        the specified columns in csv_path (specified when Chorogrid class
        initialized).
        
        Note on kwarg dicts: defaults will be used for all keys unless
        overridden, i.e. you don't need to state all the key-value pairs.
        
        kwarg: font_dict
            default: {'font-style': 'normal', 'font-weight': 'normal', 
                      'font-size': '12px', 'line-height': '125%', 
                      'text-anchor': 'middle', 'font-family': 'sans-serif', 
                      'letter-spacing': '0px', 'word-spacing': '0px', 
                      'fill-opacity': 1, 'stroke': 'none', 
                      'stroke-width': '1px', 'stroke-linecap': 'butt', 
                      'stroke-linejoin': 'miter', 'stroke-opacity': 1,
                      'fill': '#000000'}
                      
        kwarg: spacing_dict
            default: {'margin_left': 30,  'margin_top': 60,  
                      'margin_right': 40,  'margin_bottom': 20,  
                      'cell_width': 40,  'title_y_offset': 30,  
                      'name_y_offset': 15,  'roundedness': 3,  
                      'gutter': 1,  'stroke_color': '#ffffff',  
                      'stroke_width': 0, 'missing_color': '#a0a0a0',
                      'legend_offset': [0, -10]}
                      
        kwarg: font_colors
            default = "#000000"
            if specified, must be either listlike object of colors 
            corresponding to ids, a dict of hex colors to font color, or a 
            string of a single color.             
        """
        font_dict = {'font-style': 'normal', 'font-weight': 'normal', 
                      'font-size': '12px', 'line-height': '125%', 
                      'text-anchor': 'middle', 'font-family': 'sans-serif', 
                      'letter-spacing': '0px', 'word-spacing': '0px', 
                      'fill-opacity': 1, 'stroke': 'none', 
                      'stroke-width': '1px', 'stroke-linecap': 'butt', 
                      'stroke-linejoin': 'miter', 'stroke-opacity': 1}
        spacing_dict = {'margin_left': 30,  'margin_top': 60,  
                      'margin_right': 80,  'margin_bottom': 20,  
                      'cell_width': 40,  'title_y_offset': 30,  
                      'name_y_offset': 15,  'roundedness': 3,  
                      'gutter': 1,  'stroke_color': '#ffffff',  
                      'missing_color': '#a0a0a0', 'stroke_width': 0,
                      'missing_font_color': '#000000',
                      'legend_offset': [0, -10]}
       
        font_dict = self._update_default_dict(font_dict, 'font_dict', kwargs)        
        spacing_dict = self._update_default_dict(spacing_dict, 
                                                 'spacing_dict', kwargs) 
        font_colors = self._determine_font_colors(kwargs)
        font_style = self._dict2style(font_dict)
        total_width = (spacing_dict['margin_left'] + 
                       (self.df[x_column].max() + 1) * 
                       spacing_dict['cell_width'] + 
                       self.df[x_column].max() *
                       spacing_dict['gutter'] + 
                       spacing_dict['margin_right'])
        total_height = (spacing_dict['margin_top'] + 
                        (self.df[y_column].max() + 1) *
                        spacing_dict['cell_width'] + 
                        self.df[x_column].max() * 
                        spacing_dict['gutter'] + 
                        spacing_dict['margin_bottom'])
        self._make_svg_top(total_width, total_height)
        if spacing_dict['roundedness'] > 0:
            roundxy = spacing_dict['roundedness']
        else:
            roundxy = 0
        for i, id_ in enumerate(self.df[self.id_column]):
            if id_ in self.ids:
                this_color = self.colors[self.ids.index(id_)]
                this_font_color = font_colors[self.ids.index(id_)]
            else:
                this_color = spacing_dict['missing_color']
                this_font_color = spacing_dict['missing_font_color']
            across = self.df[x_column].iloc[i]
            down = self.df[y_column].iloc[i]
            x = (spacing_dict['margin_left'] + 
                 across * (spacing_dict['cell_width'] + 
                 spacing_dict['gutter']))
            y = (spacing_dict['margin_top'] + 
                 down * (spacing_dict['cell_width'] + 
                 spacing_dict['gutter']))
            style_text = ("stroke:{0};stroke-width:{1};stroke-miterlimit:4;"
                          "stroke-opacity:1;stroke-dasharray:none;fill:"
                          "{2}".format(spacing_dict['stroke_color'],
                                       spacing_dict['stroke_width'],
                                       this_color))
            this_font_style = font_style + ';fill:{}'.format(this_font_color)
            ET.SubElement(self.svg, 
                          "rect", 
                          id="rect{}".format(id_),
                          x=str(x),
                          y=str(y), 
                          ry = str(roundxy), 
                          width=str(spacing_dict['cell_width']),
                          height=str(spacing_dict['cell_width']), 
                          style=style_text)
            _ = ET.SubElement(self.svg, 
                              "text", 
                              id="text{}".format(id_),
                              x=str(x + spacing_dict['cell_width']/2),
                              y=str(y + spacing_dict['name_y_offset']), 
                              style=this_font_style)
            _.text =str(id_)
        if self.legend_params is not None and len(self.legend_params) > 0:
            self.legendsvg = ET.SubElement(self.svg, "g", transform=
                    "translate({} {})".format(total_width - 
                    spacing_dict['margin_right'] + 
                    spacing_dict['legend_offset'][0],
                    total_height - self.legend_height +
                    spacing_dict['legend_offset'][1]))
            self._apply_legend()
        self._draw_title((total_width - spacing_dict['margin_left'] - 
                          spacing_dict['margin_right']) / 2 + 
                          spacing_dict['margin_left'],
                          spacing_dict['title_y_offset'])
        
    def draw_map(self, path_column='map_path', **kwargs):
        """ Creates an SVG file based on SVG paths delineating a map, 
            with paths from the specified columns in csv_path 
            (specified when Chorogrid class initialized).
        
        Note on kwarg dict: defaults will be used for all keys unless 
        overridden, i.e. you don't need to state all the key-value pairs.
        
        Note that the map does not have an option for font_dict, as
        it will not print labels.
                      
        kwarg: spacing_dict
            # Note that total_width and total_height will depend on where 
            # the paths came from.
            # For the USA map included with this python module,
            # they are 959 and 593.
            default: {'map_width': 959, 'map_height': 593,
                        'margin_left': 10,  'margin_top': 20,  
                        'margin_right': 80,  'margin_bottom': 20,  
                        'title_y_offset': 45,
                        'stroke_color': '#ffffff', 'stroke_width': 0.5, 
                        'missing_color': '#a0a0a0',
                        'legend_offset': [0, 0]}           
        """
        spacing_dict = {'map_width': 959, 
                        'map_height': 593,
                        'margin_left': 10,  
                        'margin_top': 20,  
                        'margin_right': 80,  
                        'margin_bottom': 20,  
                        'title_y_offset': 45,
                        'stroke_color': '#ffffff', 
                        'stroke_width': 0.5, 
                        'missing_color': '#a0a0a0',
                        'legend_offset': [0, 0]}        
        spacing_dict = self._update_default_dict(spacing_dict, 
                                                 'spacing_dict', kwargs) 
        total_width = (spacing_dict['map_width'] + 
                       spacing_dict['margin_left'] + 
                       spacing_dict['margin_right'])
        total_height = (spacing_dict['map_height'] + 
                        spacing_dict['margin_top'] + 
                        spacing_dict['margin_bottom'])
        self._make_svg_top(total_width, total_height)
        translate_text = "translate({} {})".format(spacing_dict['margin_left'],
                                                   spacing_dict['margin_top'])
        self.additional_offset = [spacing_dict['margin_left'],
                                  spacing_dict['margin_top']]
        mapsvg = ET.SubElement(self.svg,
                               "g",
                               transform=translate_text)
        for i, id_ in enumerate(self.df[self.id_column]):
            path = self.df[self.df[self.id_column] == id_][path_column].iloc[0]
            if id_ in self.ids:
                this_color = self.colors[self.ids.index(id_)]
            else:
                this_color = spacing_dict['missing_color']
            style_text = ("stroke:{0};stroke-width:{1};stroke-miterlimit:4;"
                          "stroke-opacity:1;stroke-dasharray:none;fill:"
                          "{2}".format(spacing_dict['stroke_color'],
                                       spacing_dict['stroke_width'],
                                       this_color))
            ET.SubElement(mapsvg,
                          "path",
                          id=str(id_),
                          d=path,
                          style=style_text)
        if self.legend_params is not None and len(self.legend_params) > 0:
            self.legendsvg = ET.SubElement(self.svg, "g", transform=
                    "translate({} {})".format(total_width - 
                    spacing_dict['margin_right'] + 
                    spacing_dict['legend_offset'][0],
                    total_height - self.legend_height +
                    spacing_dict['legend_offset'][1]))
            self._apply_legend()
        self._draw_title((total_width - spacing_dict['margin_left'] - 
                          spacing_dict['margin_right']) / 2 + 
                          spacing_dict['margin_left'],
                          spacing_dict['title_y_offset'])

    def draw_hex(self, x_column='hex_x', y_column='hex_y', true_rows=True, **kwargs):
        """ Creates an SVG file based on a hexagonal grid, with coordinates 
        from the specified columns in csv_path (specified when Chorogrid class
        initialized).
        
        Note that hexagonal grids can have two possible layouts:
        1. 'true rows' (the default), in which:
          * hexagons lie in straight rows joined by vertical sides to east and west
          * hexagon points lie to north and south
          * the home point (x=0, y=0 from upper left/northwest) has (1,0) to its immediate east
          * the home point (0,0) shares its southeast side with (0,1)'s northwest side
          * then (0,1) shares its southwest side with (0,2)'s northeast side
          * thus odd rows are offset to the east of even rows
        2. 'true columns', in which:
          * hexagons lie in straight columns joined by horizontal sides to north and south
          * hexagon points lie to east and west
          * the home point (x=0, y=0 from upper left/northwest) has (0,1) to its immediate south
          * the home point (0,0) shares its southeast side with (1,0)'s northwest side.
          * then (1,0) shares its northeast side with (2,0)'s southwest side.
          * thus odd columns are offset to the south of even columns

        Note on kwarg dicts: defaults will be used for all keys unless 
        overridden, i.e. you don't need to state all the key-value pairs.
        
        kwarg: font_dict
            default: {'font-style': 'normal', 'font-weight': 'normal', 
                      'font-size': '12px', 'line-height': '125%', 
                      'text-anchor': 'middle', 'font-family': 'sans-serif', 
                      'letter-spacing': '0px', 'word-spacing': '0px', 
                      'fill-opacity': 1, 'stroke': 'none', 
                      'stroke-width': '1px', 'stroke-linecap': 'butt', 
                      'stroke-linejoin': 'miter', 'stroke-opacity': 1,
                      'fill': '#000000'}
                      
        kwarg: spacing_dict
            default: {'margin_left': 30,  'margin_top': 60,  
                      'margin_right': 40,  'margin_bottom': 20,  
                      'cell_width': 40,  'title_y_offset': 30,  
                      'name_y_offset': 15,  'stroke_width': 0
                      'gutter': 1,  'stroke_color': '#ffffff',  
                      'missing_color': '#a0a0a0',
                      'legend_offset': [0, -10]}
                      
        kwarg: font_colors
            default: "#000000"
            if specified, must be either listlike object of colors 
            corresponding to ids, a dict of hex colors to font color, or a 
            string of a single color.            
        """
        font_dict = {'font-style': 'normal', 
                     'font-weight': 'normal', 
                     'font-size': '12px', 
                     'line-height': '125%', 
                     'text-anchor': 'middle', 
                     'font-family': 'sans-serif', 
                     'letter-spacing': '0px', 
                     'word-spacing': '0px', 
                     'fill-opacity': 1, 
                     'stroke': 'none', 
                     'stroke-width': '1px',
                     'stroke-linecap': 'butt', 
                     'stroke-linejoin': 'miter', 
                     'stroke-opacity': 1}
        spacing_dict = {'margin_left': 30,  
                        'margin_top': 60,  
                        'margin_right': 80,  
                        'margin_bottom': 20,  
                        'cell_width': 40,  
                        'title_y_offset': 30,  
                        'name_y_offset': 15,  
                        'roundedness': 3,  
                        'stroke_width': 0,  
                        'stroke_color': '#ffffff',  
                        'missing_color': '#a0a0a0', 
                        'gutter': 1,
                        'missing_font_color': '#000000',
                        'legend_offset': [0, -10]}
        font_dict = self._update_default_dict(font_dict, 'font_dict', kwargs)
       
        spacing_dict = self._update_default_dict(spacing_dict, 
                                                 'spacing_dict', kwargs)
        font_colors = self._determine_font_colors(kwargs)
        font_style = self._dict2style(font_dict)
        if true_rows:
            total_width = (spacing_dict['margin_left'] + 
                           (self.df[x_column].max()+1.5) * 
                           spacing_dict['cell_width'] + 
                           (self.df[x_column].max()-1) *
                           spacing_dict['gutter'] + 
                           spacing_dict['margin_right'])
            total_height = (spacing_dict['margin_top'] + 
                            (self.df[y_column].max()*0.866 + 0.289) *
                            spacing_dict['cell_width'] + 
                            (self.df[y_column].max()-1) *
                            spacing_dict['gutter'] + 
                            spacing_dict['margin_bottom'])
        else:
            total_width = (spacing_dict['margin_left'] + 
                           (self.df[x_column].max()*0.75 + 0.25) * 
                           spacing_dict['cell_width'] + 
                           (self.df[x_column].max()-1) *
                           spacing_dict['gutter'] + 
                           spacing_dict['margin_right'])
            total_height = (spacing_dict['margin_top'] + 
                            (self.df[y_column].max() + 1.5) *
                            spacing_dict['cell_width'] + 
                            (self.df[y_column].max()-1) *
                            spacing_dict['gutter'] + 
                            spacing_dict['margin_bottom'])
        self._make_svg_top(total_width, total_height)
        w = spacing_dict['cell_width']
        for i, id_ in enumerate(self.df[self.id_column]):
            if id_ in self.ids:
                this_color = self.colors[self.ids.index(id_)]
                this_font_color = font_colors[self.ids.index(id_)]
            else:
                this_color = spacing_dict['missing_color']
                this_font_color = spacing_dict['missing_font_color']
            across = self.df[x_column].iloc[i]
            down = self.df[y_column].iloc[i]
            # offset odd rows to the right or down
            x_offset = 0
            y_offset = 0
            if true_rows:
                if down % 2 == 1:
                    x_offset = w/2
                x = (spacing_dict['margin_left'] + 
                     x_offset + across * (w + spacing_dict['gutter']))
                y = (spacing_dict['margin_top'] + 
                    down * (1.5 * w / sqrt(3) + spacing_dict['gutter']))
            else:
                x_offset = 0.25 * w # because northwest corner is to the east of westmost point
                if across % 2 == 1:
                    y_offset = w*0.866/2
                x = (spacing_dict['margin_left'] + 
                     x_offset + across * 0.75 * (w + spacing_dict['gutter']))
                y = (spacing_dict['margin_top'] + 
                    y_offset + down * (sqrt(3) / 2 * w + spacing_dict['gutter']))
       
            polystyle = ("stroke:{0};stroke-miterlimit:4;stroke-opacity:1;"
                         "stroke-dasharray:none;fill:{1};stroke-width:"
                         "{2}".format(spacing_dict['stroke_color'],
                                      this_color,
                                      spacing_dict['stroke_width']))
            this_font_style = font_style + ';fill:{}'.format(this_font_color)
            ET.SubElement(self.svg, 
                          "polygon", 
                          id="hex{}".format(id_),
                          points=self._calc_hexagon(x, y, w, true_rows),
                          style=polystyle)
            _ = ET.SubElement(self.svg, 
                              "text", 
                              id="text{}".format(id_),
                              x=str(x+w/2),
                              y=str(y + spacing_dict['name_y_offset']), 
                              style=this_font_style)
            _.text =str(id_)
        if self.legend_params is not None and len(self.legend_params) > 0:
            self.legendsvg = ET.SubElement(self.svg, "g", transform=
                    "translate({} {})".format(total_width - 
                    spacing_dict['margin_right'] + 
                    spacing_dict['legend_offset'][0],
                    total_height - self.legend_height +
                    spacing_dict['legend_offset'][1]))
            self._apply_legend()
        self._draw_title((total_width - spacing_dict['margin_left'] - 
                          spacing_dict['margin_right']) / 2 + 
                          spacing_dict['margin_left'],
                          spacing_dict['title_y_offset'])

    def draw_multihex(self, x_column='fourhex_x', y_column='fourhex_y', 
                      contour_column = 'fourhex_contour', 
                      x_label_offset_column = 'fourhex_label_offset_x',
                      y_label_offset_column = 'fourhex_label_offset_y',
                      **kwargs):
        """ Creates an SVG file based on a hexagonal grid, with contours
            described by the following pattern:
                a: up and to the right
                b: down and to the right
                c: down
                d: down and to the left
                e: up and to the left
                f: up
            Capital letters signify a move without drawing.
        
        Note on kwarg dicts: defaults will be used for all keys unless 
        overridden, i.e. you don't need to state all the key-value pairs.
        
        kwarg: font_dict
            default: {'font-style': 'normal', 'font-weight': 'normal', 
                      'font-size': '12px', 'line-height': '125%', 
                      'text-anchor': 'middle', 'font-family': 'sans-serif', 
                      'letter-spacing': '0px', 'word-spacing': '0px', 
                      'fill-opacity': 1, 'stroke': 'none', 
                      'stroke-width': '1px', 'stroke-linecap': 'butt', 
                      'stroke-linejoin': 'miter', 'stroke-opacity': 1,
                      'fill': '#000000'}
                      
        kwarg: spacing_dict
            default: {'margin_left': 30,  'margin_top': 60,  
                      'margin_right': 40,  'margin_bottom': 20,  
                      'cell_width': 30,  'title_y_offset': 30,  
                      'name_y_offset': 15,  'stroke_width': 1
                      'stroke_color': '#ffffff',  'missing_color': '#a0a0a0',
                      'legend_offset': [0, -10]}
            (note that there is no gutter)
                      
        kwarg: font_colors
            default = "#000000"
            if specified, must be either listlike object of colors 
            corresponding to ids, a dict of hex colors to font color, or a 
            string of a single color.           
        """
        font_dict = {'font-style': 'normal', 
                     'font-weight': 'normal', 
                     'font-size': '12px', 
                     'line-height': '125%', 
                     'text-anchor': 'middle', 
                     'font-family': 'sans-serif', 
                     'letter-spacing': '0px', 
                     'word-spacing': '0px', 
                     'fill-opacity': 1, 
                     'stroke': 'none', 
                     'stroke-width': '1px',
                     'stroke-linecap': 'butt', 
                     'stroke-linejoin': 'miter', 
                     'stroke-opacity': 1}
        spacing_dict = {'margin_left': 30,  
                        'margin_top': 60,  
                        'margin_right': 80,  
                        'margin_bottom': 20,  
                        'cell_width': 30,  
                        'title_y_offset': 30,  
                        'name_y_offset': 15,  
                        'roundedness': 3,  
                        'stroke_width': 1,  
                        'stroke_color': '#ffffff',  
                        'missing_color': '#a0a0a0', 
                        'missing_font_color': '#000000',
                        'legend_offset': [0, -10]}
        font_dict = self._update_default_dict(font_dict, 'font_dict', kwargs)
       
        spacing_dict = self._update_default_dict(spacing_dict, 
                                                 'spacing_dict', kwargs)
        font_colors = self._determine_font_colors(kwargs)
        font_style = self._dict2style(font_dict)
        total_width = (spacing_dict['margin_left'] + 
                       (self.df[x_column].max()+1.5) * 
                       spacing_dict['cell_width'] + 
                       spacing_dict['margin_right'])
        total_height = (spacing_dict['margin_top'] + 
                        (self.df[y_column].max() + 1.711) *
                        spacing_dict['cell_width'] + 
                        spacing_dict['margin_bottom'])
        self._make_svg_top(total_width, total_height)
        w = spacing_dict['cell_width']
        h = w/sqrt(3)
        for i, id_ in enumerate(self.df[self.id_column]):
            if id_ in self.ids:
                this_color = self.colors[self.ids.index(id_)]
                this_font_color = font_colors[self.ids.index(id_)]
            else:
                this_color = spacing_dict['missing_color']
                this_font_color = spacing_dict['missing_font_color']
            across = self.df[x_column].iloc[i]
            down = self.df[y_column].iloc[i]
            contour = self.df[contour_column].iloc[i]
            label_off_x = self.df[x_label_offset_column].iloc[i]
            label_off_y = self.df[y_label_offset_column].iloc[i]
            # offset odd rows to the right
            if down % 2 == 1:
                x_offset = w/2
            else:
                x_offset = 0
       
            x = (spacing_dict['margin_left'] + 
                 x_offset + across * w)
            y = (spacing_dict['margin_top'] + 
                 down * (1.5 * w / sqrt(3)))
            polystyle = ("stroke:{0};stroke-miterlimit:4;stroke-opacity:1;"
                         "stroke-dasharray:none;fill:{1};stroke-width:"
                         "{2}".format(spacing_dict['stroke_color'],
                                      this_color,
                                      spacing_dict['stroke_width']))
            this_font_style = font_style + ';fill:{}'.format(this_font_color)
            ET.SubElement(self.svg, 
                          "path", 
                          id="hex{}".format(id_),
                          d=self._calc_multihex(x, y, w, contour),
                          style=polystyle)
            _ = ET.SubElement(self.svg, 
                              "text", 
                              id="text{}".format(id_),
                              x=str(x + w/2 + w * label_off_x),
                              y=str(y + spacing_dict['name_y_offset'] +
                                    h * label_off_y), 
                              style=this_font_style)
            _.text =str(id_)
        if self.legend_params is not None and len(self.legend_params) > 0:
            self.legendsvg = ET.SubElement(self.svg, "g", transform=
                    "translate({} {})".format(total_width - 
                    spacing_dict['margin_right'] + 
                    spacing_dict['legend_offset'][0],
                    total_height - self.legend_height +
                    spacing_dict['legend_offset'][1]))
            self._apply_legend()
        self._draw_title((total_width - spacing_dict['margin_left'] - 
                          spacing_dict['margin_right']) / 2 + 
                          spacing_dict['margin_left'],
                          spacing_dict['title_y_offset'])

    def draw_multisquare(self, x_column='multisquare_x', y_column='multisquare_y', 
                      contour_column = 'multisquare_contour', 
                      x_label_offset_column = 'multisquare_label_offset_x',
                      y_label_offset_column = 'multisquare_label_offset_y',
                      **kwargs):
        """ Creates an SVG file based on a square grid, with contours
            described by the following pattern:
                a: right
                b: down
                c: left
                d: up
                A: right (without drawing)
                B: down (without drawing)
                C: left (without drawing)
                D: up (without drawing)

        Note on kwarg dicts: defaults will be used for all keys unless 
        overridden, i.e. you don't need to state all the key-value pairs.
        
        kwarg: font_dict
            default: {'font-style': 'normal', 'font-weight': 'normal', 
                      'font-size': '12px', 'line-height': '125%', 
                      'text-anchor': 'middle', 'font-family': 'sans-serif', 
                      'letter-spacing': '0px', 'word-spacing': '0px', 
                      'fill-opacity': 1, 'stroke': 'none', 
                      'stroke-width': '1px', 'stroke-linecap': 'butt', 
                      'stroke-linejoin': 'miter', 'stroke-opacity': 1,
                      'fill': '#000000'}
                      
        kwarg: spacing_dict
            default: {'margin_left': 30,  'margin_top': 60,  
                      'margin_right': 40,  'margin_bottom': 20,  
                      'cell_width': 30,  'title_y_offset': 30,  
                      'name_y_offset': 15,  'stroke_width': 1
                      'stroke_color': '#ffffff',  'missing_color': '#a0a0a0',
                      'legend_offset': [0, -10]}
            (note that there is no gutter)
                      
        kwarg: font_colors
            default = "#000000"
            if specified, must be either listlike object of colors 
            corresponding to ids, a dict of hex colors to font color, or a 
            string of a single color.           
        """
        font_dict = {'font-style': 'normal', 
                     'font-weight': 'normal', 
                     'font-size': '12px', 
                     'line-height': '125%', 
                     'text-anchor': 'middle', 
                     'font-family': 'sans-serif', 
                     'letter-spacing': '0px', 
                     'word-spacing': '0px', 
                     'fill-opacity': 1, 
                     'stroke': 'none', 
                     'stroke-width': '1px',
                     'stroke-linecap': 'butt', 
                     'stroke-linejoin': 'miter', 
                     'stroke-opacity': 1}
        spacing_dict = {'margin_left': 30,  
                        'margin_top': 60,  
                        'margin_right': 80,  
                        'margin_bottom': 20,  
                        'cell_width': 30,  
                        'title_y_offset': 30,  
                        'name_y_offset': 15,  
                        'roundedness': 3,  
                        'stroke_width': 1,  
                        'stroke_color': '#ffffff',  
                        'missing_color': '#a0a0a0', 
                        'missing_font_color': '#000000',
                        'legend_offset': [0, -10]}
        font_dict = self._update_default_dict(font_dict, 'font_dict', kwargs)
        spacing_dict = self._update_default_dict(spacing_dict, 
                                                 'spacing_dict', kwargs)
        font_colors = self._determine_font_colors(kwargs)
        font_style = self._dict2style(font_dict)
        total_width = (spacing_dict['margin_left'] + 
                       (self.df[x_column].max()+1) * 
                       spacing_dict['cell_width'] + 
                       spacing_dict['margin_right'])
        total_height = (spacing_dict['margin_top'] + 
                        (self.df[y_column].max()+1) *
                        spacing_dict['cell_width'] + 
                        spacing_dict['margin_bottom'])
        self._make_svg_top(total_width, total_height)
        w = spacing_dict['cell_width']
        for i, id_ in enumerate(self.df[self.id_column]):
            if id_ in self.ids:
                this_color = self.colors[self.ids.index(id_)]
                this_font_color = font_colors[self.ids.index(id_)]
            else:
                this_color = spacing_dict['missing_color']
                this_font_color = spacing_dict['missing_font_color']
            across = self.df[x_column].iloc[i]
            down = self.df[y_column].iloc[i]
            contour = self.df[contour_column].iloc[i]
            label_off_x = self.df[x_label_offset_column].iloc[i]
            label_off_y = self.df[y_label_offset_column].iloc[i]
       
            x = (spacing_dict['margin_left'] + across * w)
            y = (spacing_dict['margin_top'] + 
                 down * w)
            polystyle = ("stroke:{0};stroke-miterlimit:4;stroke-opacity:1;"
                         "stroke-dasharray:none;fill:{1};stroke-width:"
                         "{2}".format(spacing_dict['stroke_color'],
                                      this_color,
                                      spacing_dict['stroke_width']))
            this_font_style = font_style + ';fill:{}'.format(this_font_color)
            ET.SubElement(self.svg, 
                          "path", 
                          id="square{}".format(id_),
                          d=self._calc_multisquare(x, y, w, contour),
                          style=polystyle)
            _ = ET.SubElement(self.svg, 
                              "text", 
                              id="text{}".format(id_),
                              x=str(x + w/2 + w * label_off_x),
                              y=str(y + spacing_dict['name_y_offset'] +
                                    w * label_off_y), 
                              style=this_font_style)
            _.text = str(id_)
        if self.legend_params is not None and len(self.legend_params) > 0:
            self.legendsvg = ET.SubElement(self.svg, "g", transform=
                    "translate({} {})".format(total_width - 
                    spacing_dict['margin_right'] + 
                    spacing_dict['legend_offset'][0],
                    total_height - self.legend_height +
                    spacing_dict['legend_offset'][1]))
            self._apply_legend()
        self._draw_title((total_width - spacing_dict['margin_left'] - 
                          spacing_dict['margin_right']) / 2 + 
                          spacing_dict['margin_left'],
                          spacing_dict['title_y_offset'])
