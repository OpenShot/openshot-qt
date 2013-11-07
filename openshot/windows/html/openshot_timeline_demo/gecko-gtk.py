#!/usr/bin/env python

import gtk
import gtkmozembed

def CloseWindow(caller_widget):
    """Close the window and exit the app"""
    gtk.main_quit() # Close the app fully

# Set-up the main window which we're going to embed the widget into
win = gtk.Window() # Create a new GTK window called 'win'

win.set_title("Simple Web Browser") # Set the title of the window
win.set_icon_from_file('/usr/share/icons/Tango/22x22/apps/web-browser.png') # Set the window icon to a web browser icon
win.set_position(gtk.WIN_POS_CENTER) # Position the window in the centre of the screen

win.connect("destroy", CloseWindow) # Connect the 'destroy' event to the 'CloseWindow' function, so that the app will quit properly when we press the close button

# Create the browser widget
gtkmozembed.set_profile_path("/tmp", "simple_browser_user") # Set a temporary Mozilla profile (works around some bug)
mozbrowser = gtkmozembed.MozEmbed() # Create the browser widget

# Set-up the browser widget before we display it
win.add(mozbrowser) # Add the 'mozbrowser' widget to the main window 'win'
mozbrowser.load_url("file:///home/jonathan/apps/openshot_timeline/timeline.html") # Load a web page
#mozbrowser.load_url("http://jqueryui.com/demos/") # Load a web page
mozbrowser.set_size_request(800,600) # Attempt to set the size of the browser widget to 600x400 pixels
mozbrowser.show() # Try to show the browser widget before we show the window, so that the window appears at the correct size (600x400)

win.show() # Show the window

gtk.main() # Enter the 'GTK mainloop', so that the GTK app starts to run