# -*- coding: utf-8 -*-
r"""Contains functions for visualizing time profiles of simulation results"""
from warnings import warn
import altair as alt
from six import iteritems
from mass.core.mass_configuration import MassConfiguration

MASSCONFIGURATION = MassConfiguration()
# function to make xlim
def set_xlim(xlim):
    source=conc_sol.to_frame()
    data = source
    data = data.reset_index().melt('Time', var_name='Metabolites', value_name='Concentrations')
    if xlim == None:
        xlim_max=data['Time'].iloc[-1]
        xlim=[1e-5,xlim_max]

    else:
        xlim=xlim
    return xlim

#function to make ylim 
def set_ylim(ylim):
    source=conc_sol.to_frame()
    data = source
    data = data.reset_index().melt('Time', var_name='Metabolites', value_name='Concentrations')
    
    if ylim == None:
        conc=data['Concentrations']
        ylim_max=max(conc)
        ylim=[1e-5,ylim_max]
    else:
        ylim=ylim
    return ylim


#function to make plot typelinear log
def set_plot_type(plot_type):
    if plot_type == None:
        x_plot_type = 'log'
        y_plot_type = 'log'
    elif plot_type == "logx":
        x_plot_type = 'log'
        y_plot_type = 'linear'
    elif plot_type == "logy":
        x_plot_type = 'linear'
        y_plot_type = 'log'
    elif plot_type == "linear":
        x_plot_type = 'linear'
        y_plot_type = 'linear'
    elif plot_type == "logxlogy":
        x_plot_type = 'log'
        y_plot_type = 'log'
    return x_plot_type,y_plot_type



#function to set x label and y label
def set_x_label(xlabel):
    if xlabel==None:
        xlabel="Time"
    else:
        xlabel=xlabel
    return xlabel
        
def set_y_label(ylabel):        
    if ylabel==None:
        ylabel="Concentrations"
    else:
        ylabel=ylabel
    return ylabel


#new
def plot_conc_sol(mass_solution, observable=None, interactive = False, xlim=None,ylim=None,plot_type=None,xlabel=None,
                  ylabel=None,width=None,height=None):
    
    """Generate an interactable time profile which can zoom into the plot with interactive tooltip"""

    source=conc_sol.to_frame()
    data = source
    if observable == None or observable == "all":
        data=data
    else:
        data = data[observable]
    if interactive== True and observable == None:
        raise Exception("visualisation will be very glitchy, if you want to proceed with all, make observable=""all""") 

    data = data.reset_index().melt('Time', var_name='Metabolites', value_name='Concentrations')
    alt.data_transformers.disable_max_rows()

    xlim=set_xlim(xlim)
    ylim=set_ylim(ylim)
        
       
    # Setting type of plot
    x_plot_type=set_plot_type(plot_type)[0]
    y_plot_type=set_plot_type(plot_type)[1]
        
    # Setting x label and y label
    xlabel=set_x_label(xlabel)
    ylabel=set_y_label(ylabel)
    
    # Setting width and height
    if width == None:
        width=500
    else:
        width=width
        
    if height == None:
        height=400
    else:
        height=height
     
    selection = alt.selection_multi(fields=['Metabolites'])

    color = alt.condition(selection,
                    alt.Color('Metabolites:N', legend=None,
                        scale=alt.Scale(scheme='rainbow')),
                    alt.value('lightgray'))



    line = alt.Chart(data).mark_line(clip=True).encode(
    alt.X('Time:Q',
    scale=alt.Scale(type = x_plot_type, domain = xlim,
#                   zero=True,
                        ),axis=alt.Axis(tickCount=5)),
    alt.Y('Concentrations:Q',title=ylabel,scale=alt.Scale(type=y_plot_type,
    padding = 10,domain = ylim,
#                   zero=True, 
                        ),axis=alt.Axis(grid=False,tickCount=5)),
    color=color
    ).properties(width=width, height=height)

    legend = alt.Chart(data).mark_point(size=100).encode(
    y=alt.Y('Metabolites:N', axis=alt.Axis(orient='right')),
    color=color).add_selection(selection)


    #   multi line tooltip
    nearest = alt.selection(type='single', nearest=True, on='mouseover',
                    fields=['Time'])

    if interactive == False: 
        line = line.encode(tooltip= ["Metabolites"]+["Time"]+["Concentrations"])


        final=alt.layer(
        line).properties(
        width=500, height=500)

        final=line|legend 
        # make note that shift click clicks multiple 

    else:
        legend = legend.encode(alt.Shape('Metabolites:N', legend=None))

        # Transparent selectors across the chart. This is what tells us # the x-value of the cursor
        selectors = alt.Chart(data).mark_point().encode(alt.Color('Metabolites:N', legend=None),
            x='Time:Q',
            opacity=alt.value(0),
        ).add_selection(
            nearest
        )
            # Draw points on the line, and highlight based on selection
        points = line.mark_point(size=100).encode(alt.Shape('Metabolites:N', legend=None),
            opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
        ).interactive()

        # Draw text labels near the points, and highlight based on selection
        text = line.mark_text(align='left', dx=8, dy=12).encode(
            text=alt.condition(nearest, 'Concentrations:Q', alt.value(' '))
        )
        # Draw a rule at the location of the selection
        rules = alt.Chart(data).mark_rule(color='gray').encode(
            x='Time:Q',
        ).transform_filter(
            nearest
        ) 
        final=alt.layer(
            line, selectors, points, rules, text
        ).properties(
            width=500, height=500)
        final= final | legend

    return final