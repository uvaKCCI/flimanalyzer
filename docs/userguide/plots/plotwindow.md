# The Plot Window

Each plot opens in a plot window. Its name starts with `Plot:`, and it is listed in the `Window` menu (see [Result windows](/userguide/dialogs.md#result-windows)). In the plot window you can zoom into the plot, change its axes, labels and line colors, and save it as an image file.

## The Navigation Toolbar

![](/images/analysis/plotwindow.png)

The toolbar at the bottom of the plot window is the navigation toolbar of matplotlib, the library that draws the plots. It has these buttons, from left to right:

- `Home`: goes back to the original view of the plot.
- `Back` and `Forward`: go back to the previous view, or forward to the next one, after you zoomed or moved the plot.
- `Pan`: move the plot with the left mouse button. Drag with the right mouse button to zoom in or out. Hold down `x` or `y` to move along that axis only.
- `Zoom`: drag a rectangle with the left mouse button to zoom into it. Hold down `x` or `y` to zoom along that axis only.
- `Subplots`: opens matplotlib's `Configure subplots` window, to change the margins and the spacing of the plots in the figure.
- `Save`: saves the figure in a file, see [Saving a Plot](#saving-a-plot).

`Pan` and `Zoom` stay on until you click the button again. When the mouse is over a plot, the right end of the toolbar shows the x and y values at the mouse position.

## Saving a Plot

Click `Save` in the toolbar. In the file dialog, choose the folder and the file name, and the file type, for example PNG, PDF, SVG or TIFF. The plot is saved with the current view and with the changes you made in the window.

To save the plots automatically each time a tool runs, check `Save results in` in the tool's dialog. The plots are then saved as PNG files (see [Saving results](/userguide/dialogs.md#saving-results)).

## Changing Axes, Labels and Lines

Double-click parts of a plot to change them:

- **An axis:** double-click just outside the plot, along the x or the y axis. The `Set X Axis` or `Set Y Axis` dialog opens. Set the axis `label` and its `min` and `max` values, and click `OK`.

    ![](/images/analysis/plot-setaxis.png)

- **A text,** such as the title of a plot or an axis label: the `Update Label` dialog opens. Type the new text and click `OK`.
- **A line,** such as a curve of a KDE plot or a line of a line plot: a color dialog opens. Choose the new color of the line.

```{note}
Double-click editing is not available in plots of the `Heatmap` and `Pair Plot` tools. The navigation toolbar and saving work in all plot windows.
```

The changes apply only to the plot window. They are not kept when you run the tool again.
