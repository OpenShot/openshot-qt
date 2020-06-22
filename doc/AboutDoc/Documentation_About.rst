.. Copyright (c) 2008-2020 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

.. OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

.. OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

.. You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.

.. _Documentation_ref:

About the documentation
=======================

The source files for the manual are all found in the project repository, `(the doc/ directory) <https://github.com/OpenShot/openshot-qt/tree/develop/doc>`_ 

The documentation is written in reStructured Text, or ReST. 
This is a plain text format encoded in UTF-8.
It contains special syntax so formatting can be applied by third-party tools.
Sphinx is the tool used by OpenShot to create the manual.

You can suggest improvements or submit small changes for our documentation on our Github here: 
https://github.com/OpenShot/openshot-qt/issues/2989

.. todo:: 
  **Discuss if this is needed/desired and if Reddit threads can be pinned to top. **
  Todo: Reddit thread to be made, bookmarked?, add hyperlink
  finish line: Or in `this<url>`_ reddit thread. 
  
The preferred method for submitting large edits would be via GitHub Pull Request. 
But we can make accommodations for anyone who would like to contribute but is not familiar with version-control systems like Git.

License
-------
Project documentation is licensed under the same license as the source code.
Specifically, the GNU General Public License version 3 or higher (GPLv3+); see the document header.
Is is also allows the the documentation to ger prosessed in other tools before it reaches its final form.

Github
------
In the issue tracker, subjects that contain explanations that should probably be included in the documentation can be labeled `docs <https://github.com/OpenShot/openshot-qt/issues?q=label%3Adocs+>`_\ .
Questions that are answered often in Github  can be tagged `FAQ <https://github.com/OpenShot/openshot-qt/issues?q=label%3AFAQ+>`_ 
and can be added to the `Wiki FAQ <https://github.com/OpenShot/openshot-qt/wiki/FAQ>`_ or better explained in the manual.
Reddit has topic `Addressing Common Issues <https://www.reddit.com/r/OpenShot/wiki/commonproblems>`_  pinned on the right.


 |  Tutorials for how to add changes to Github: 
 |  Github on Pull requests: https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request-from-a-fork
 |  Github text howto: https://opensource.com/life/16/3/submit-github-pull-request
 |  Github video howto: https://www.youtube.com/watch?v=rgbCcBNZcdQ

It is possible to edit files directly in the Github web interface.
To edit a file via the web interface,
you can just click the pencil icon in its upper-right corner.

When you started editing,
Github would see that you do not have permissions to make changes directly to files here.
So it would set you up with a copy ("fork") under your account,
where you can make changes before submitting them as a Pull Request.

Editing on the web is perfectly workable.
Rest files are automatically recognized by Github, to view the plain text version click on **raw** or the **edit** button. 
A workflow test is included in the repo, and will be included in the fork. However, you will need to activate this under **Actions**
Once activated, it will automatically run after every commit. 
It will also generate the HTML version of the documentation as a so-called *artifact*, 
and can be downloaded as ZIP package under the workflow event in the *Action* page. 

With a local clone you can use a previewing editor or
(if you have the necessary Sphinx tools installed)
generate updated HTML docs and view them in a web browser.

Sphinx
------
`Spinx <https://www.sphinx-doc.org/en/master/>`_ was created to simply generate documentation from Python sourcecode.
It is written in Python, and also used in other environments. 
It is licensed under the BSD license.
Generating a local copy of the manual requires only the Python-based Sphinx documentation system and the Sphinx RTD theme.  
They can be installed  using most package managers, or via 

.. code-block:: console

  pip3 install sphinx sphinx-rtd-theme

Anyone who would like to contribute and needs help with installing and using Sphinx can ask for support in the issues tracker.

Tutorial video:	https://www.youtube.com/watch?v=ouHVkMo3gwE

ReST Basic Syntax
-----------------
.. TODO::  `List of basic/custom syntax </Documentation_RestSyntax.rst>`_  in Openshot documentation.  

- Some explanation here:  https://hyperpolyglot.org/lightweight-markup
- or here: https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html
- Sphinx ReST details https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#gotchas
- Video tutorials here:  https://www.youtube.com/results?search_query=restructuredtext+tutorial

Most text editors with syntax highlighting and checking include a ReST language mode or templates can be added. 

A crossplatfom ReST editor with automatic HTML previewing. is ATOM: https://atom.io/
A Notepad++ ReST template:	https://github.com/steenhulthin/reStructuredText_NPP
 

File naming and directory structure
-----------------------------------

Documentation files are stored in the ``doc/`` directory of the project repository.
Each source file represents one chapter of the User Guide.
The filename is the chapter title, with any spaces replaced by underscores (``_``).
ReStructuredText files have the extension ``.rst``.
Images used in the documentation are in the ``doc/images`` subdirectory. 

.. caution::

   Documentation filenames must not contain spaces, as they cause problems for Sphinx.



File structure
--------------

Every file starts with a hidden 4 paragraph block of the standard header. 
It contains the Copyright notice, description of OpenShot,  disclaimer and License notice. 
(See `template <template.rst>`_ )
It is sometimes followed by a referral anchor for the title. 

The content starts with a chapter title, double-underlined using equals signs (``=====``).
This is followed by a short introduction describing what will be covered in the chapter.

A chapter may be divided into sections and subsections, each beginning with an underlined heading.
Like the chapter title, section headings are double-underlined using equals signs.
Subsection headings are single-underlined using hyphens (``----``).

.. code-block:: ReST

    Chapter title
    =============

    Introduction paragraph.
    
    Section heading
    ===============
    
    Subsection heading
    ------------------

Sentences should be written one sentence per line, and do not need to end on a space.
The markup language then flows them all together into paragraphs when it generates the formatted docs.
You can also break at other logical points, like after a comma in a longer sentence,
or before starting an inline markup command.
It is a guideline, not a rule.
This tends to be a pretty good fit for any sort of written prose, when it is in a markup language like ReST and managed in a version control system.

There are four reasons for this:

- Writing that way, there is no worrying about line length or when to wrap. 
- The diffs when changes are submitted also tend to be more readable and focused. 
- It encourages shorter, simpler sentences which is a good thing when writing docs. 
- Short lines are easier to translate as they are less likely to be changed. 

Comments for why things are documented a certain way can be hidden after a double dot and start with "NOTE: ". 
They may contain a link to a relevant issue in the tracker for more information. 

But comments regarding issues that are not complete (like new features) should be marked with the tag \.. TODO::
They will be emphasized by Github but filtered out of the final user documentation by Sphinx. 



.. todo:: 
  ** After finding out how translation files can be created, update this paragraph.**

  Translation
  -----------
  
  Translation files are generated and managed by Sphinx.
  If the images are not translated, they will default back to the original.
  Filenames do not get translated.
  There may be translation notes hidden in the documentation, blocked out with \.. TRANSLATION NOTE: 
  Files for translation will be hosted at `Launchpad <https://translations.launchpad.net/openshot/2.0/+translations>`_.
  When translating numbers referencing a screenshot in non-western languages, please make sure to update the screenshot too. 
  If available, images of the translation should be saved in their subdirectory *(to be decided)* 

  .. TODO:: Add subdirectory

  .. TRANSLATION NOTE: After translating tables make sure they do not break. The underlining of table rows needs to be the same length as the new words. 
  

Images
------

.. caution:: Please make sure to add your images under the GPL3 as well.

**PNG** is the preferred format for screenshots, as it's not subject to compression artifacts the way JPG is. 
JPG is fine too, if the quality is high enough (Compression of 90% or better). 
Clarity is the priority, not file size. 

Animated GIFs are not suitable as screenshots, because the animated component is only visible when the docs are viewed in web form. 
Also the quality and/or file size ratio tends to be abysmal and thus multi-megabyte GIFs can take forever to download and start animating. 
They are however suitable as alternative to Video. 

Images should be **696px wide** at their **maximum**. 
The page layout has a width cap that makes it the effective maximum width for images. 
For this reason 4:3 pictures are preferred over widescreen. 
Images should be whatever shape they need to be in order to show the necessary information, there is no fixed aspect.
But since images will be scaled to fit the width of the page, in general images should not be unnecessarily wide. 
Otherwise they can end up too small when displayed.

.. TODO:: Image width Verification Needed: 
  Is this set in the server? Does it apply to all browsers? Does this apply to offline docs too?
  From a test by ferdnyc "when I have a Chrome window open with the manual loaded into it, once the window hits about 1160px wide, that's it — the content stops getting any wider. Past that width (which is including the sidebar), the only thing that grows is the empty space to the right of the content container. And at that size, the images are scaled to 696px wide."
  https://github.com/OpenShot/openshot-qt/issues/2989

There is no demo art package available for screenshots. 
Screenshots showing different content is an opportunity to illustrate the variety of different features and configurations available.
However during a step-by-step tutorial for a feature, it makes sense to have a set of consistent imports for all of the steps. 
So that the illustrations reflect exactly what the user would expect to see in the actual software.

Images should be named descriptively, so the names have relevance long-term.
It should say what it is, and it should be what it says. 
I suitable, they can be named for the tutorial page they belong to. 

They can be named for Action-WindowName or ActionStepNumber. 
Images belonging to a sequence should be numbered. 
Names like intro-tutorial-step-1.png (followed by -step-2.png through -step-n.png), 
interface-export-simple.png and so on. 

.. TODO:: QUESTION: Should image sequences be in the same resolution? So they can be combined to animation?

Tutorial art
------------
The color for arrows is *#aec255ff*

The green contrasts well with the dark GUI of Openshot
The font used in the art is *Ubuntu* and can be found in the repo or the Openshot installation. 

There is a green call-out circle  used for numbering in the repo under docs/images/circle.svg. 
It is editable in software that can edit SVG files (e.g. Inkscape and Illustrator). 
The green arrow is not yet in the repo.

.. TODO:: PROPOSAL: save all tutorial art into docs/pointers/ or something like that?
.. TODO:: Upload font and callout circle to dir
.. TODO:: Question: because it is an SVG, is the number changed in ReST?

Video
-----
The manual should ideally be useful in print form as well,
but for extra clarification a video or GIF can be included.
Any animated elements should enhance the information presented in the static content, rather than replace it. 
Whatever happens in the animation should also be described in full detail in the accompanying text.
So make sure a description and pictures are suitable for offline documentation first. 

Video may be preferable over animated GIF, because embedded videos are clearer and higher quality.
They are also click-to-play which avoids forcing a large initial download on the user. 
For short actions, GIFS may however be a lot easier. 

Beside GIF, only Youtube videos can be embedded with the tag
\.. youtube \:: 

.. NOTE: https://github.com/OpenShot/openshot-qt/pull/3394

Tables
------

.. TODO:: Table specifications

| Todo: Issues with tables
| https://github.com/OpenShot/openshot-qt/issues/1262
| https://github.com/OpenShot/openshot-qt/pull/1272

