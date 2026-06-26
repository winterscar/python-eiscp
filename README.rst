python-eiscp
===============

|Build Status| |GitHub release| |PyPI|

This is a Python package to interface with
Onkyo receivers.

This package was created primarily to replace `onkyo-eiscp <https://github.com/miracle2k/onkyo-eiscp/>` which is used in the media_player
platform for the `Home Assistant <https://home-assistant.io/>`__
automation platform but it is structured to be general-purpose and
should be usable for other applications as well.

The structure of this code is _very_ heavily inspired by the `Python Anthem library <https://github.com/nugget/python-anthemav/>` and the protocol used
is copied directly from the onkyo-eiscp library. Go check there to see how it works.

In this library, you send requests as per the onkyo-eiscp spec (volume=55)
and then ... nothing. All requests are fire and forget. To understand what's
happening with the reciever, you'll need to provide a callback_function that
gets called whenever something changes on the reciever.

Your callback function will recieve a tuple consisting of 3 values (a triple?):
zone: [main, zone1, zone2, zone3, zone4, dock]
name: (volume, power, etc..)
value: (volume_up, 55, tv)

I essentially mashed the two projects together and it seems to work so 🤷‍♂️...

Requirements
------------

-  Python 3.4 or newer with asyncio
-  An Onkyo reciever


Installation
------------

You can, of course, just install the most recent release of this package
using ``pip``. This will download the more rececnt version from
`PyPI <https://pypi.python.org/pypi/pyeiscp>`__ and install it to your
host.

::

   pip install pyeiscp

If you want to grab the the development code, you can also clone this
git repository and install from local sources:

::

   cd py-eiscp
   pip install .

And, as you probably expect, you can live the developer’s life by
working with the live repo and edit to your heart’s content:

::

   cd py-eiscp
   pip install . -e

Testing
-------

The package installs a command-line tool which will connect to your
receiver, power it up, and then monitor all activity and changes that
take place. The code for this console monitor is in
``pyeiscp/tools.py`` and you can invoke it by simply running this at
the command line with the appropriate IP and port number that matches
your receiver and its configured port:

::

   eiscp_monitor --host 10.0.0.100 --port 60128

A secondary command line tool allows for easy sending of commands to
the receiver. For example, to query the multiroom audio status ("groups")
on an Onkyo receiver:

::

   eiscp_sender --host 10.0.0.100 'multiroom-status query'

The eiscp_sender command can also be used to enable/disable multiroom audio
aka (flareconnect). For this you will need the mac address of the secondary
device, you can obtain this from the <deviceid> field returned from the
'multiroom-status query' command. To start a multiroom audio group with 
10.0.0.100 (0123456DDEEFF) as the host, and 012356AABBCC as secondary device:

::

   eiscp_sender --host 10.0.0.100 'raw-message=<mgs zone="1"><groupid>1</groupid><maxdelay>500</maxdelay><devices><device id="012356AABBCC" zoneid="1"/><device id="0123456DDEEFF" zoneid="1"/></devices></mgs>'

To stop this grouping:

::

   eiscp_sender --host 10.0.0.100 'raw-message=<mgs zone="1"><groupid>0</groupid></mgs>'


Credits
-------

-  Most of this package was written by David McNett.

   -  https://github.com/nugget
   -  https://keybase.io/nugget
- Pretty much everything else was written by @miracle2k
- I just mushed it all together.

How can you help?
-----------------

-  First and foremost, you can help by forking this project and coding.
   Features, bug fixes, documentation, and sample code will all add
   tremendously to the quality of this project.

-  If you have a feature you’d love to see added to the project but you
   don’t think that you’re able to do the work, I’m someone is probably
   happy to perform the directed development in the form of a bug or
   feature bounty.

-  If you’re anxious for a feature but it’s not actually worth money to
   you, please open an issue here on Github describing the problem or
   limitation. If you never ask, it’ll never happen

-  If you just want to thank me for the work I’ve already done, I’m
   happy to accept your thanks, gratitude, pizza, or bitcoin. My bitcoin
   wallet address can be on `Keybase <https://keybase.io/nugget>`__ or
   you can send me a donation via
   `PayPal <https://www.paypal.me/macnugget>`__.

-  Or, if you’re not comfortable sending me money directly, I’ll be
   nearly as thrilled (really) if you donate to `the
   ACLU <https://action.aclu.org/donate-aclu>`__,
   `EFF <https://supporters.eff.org/donate/>`__, or
   `EPIC <https://epic.org>`__ and let me know that you did.

.. |Build Status| image:: https://travis-ci.org/nugget/python-anthemav.svg?branch=master
   :target: https://travis-ci.org/nugget/python-anthemav
.. |GitHub release| image:: https://img.shields.io/github/release/nugget/python-anthemav.svg
   :target: https://github.com/nugget/python-anthemav/releases
.. |PyPI| image:: https://img.shields.io/pypi/v/anthemav.svg
   :target: https://pypi.python.org/pypi/anthemav
