Onkyo audio groups in home assistant
====================================

This is a crude guide on how to set up Onkyo flareconnect (aka multiroom audio / audio groups) with home assistant. For this we will replace the python-eiscp (pyeiscp) module used by the Onkyo integration in home assistant with a modified version. You can find the details on this modded version here: https://github.com/rlKoekie/python-eiscp/tree/onkyo-groups . The goal here is to create two simple buttons on your home assistant dashboard for easily starting and stopping the Onkyo audio group setup.

My own instance is a Home Assistant OS, running under libvirt on linux (virsh). Things might be slightly different depending on your own setup (e.g. docker). In these cases you will need to make sure you connect to the right docker container command line.
You will of course need two (or more) Onkyo devices with multiroom audio support (flareconnect), you can use the “Onkyo Controller” app on android ( https://play.google.com/store/apps/details?id=com.onkyo.jp.onkyocontroller ) to check and test this, or you can just YOLO it. The app has this feature under “edit group”.

Preparations
------------

Home Assistant installed addons:
- Advanced SSH & Web Terminal (protection mode is disabled, might not be needed)
- File editor

I am assuming that you already have your onkyo hardware configured under the home assistant “devices” under settings.

To make your own life a lot easier, you should configure your onkyo devices to have a fixed IP address. This is done in your router settings, usually in the DHCP configuration part.

Installation
------------

First we will install the modified python-eiscp module and then try the commands in the terminal, that makes it easier to debug things. After this we will define aliasses for the commands in the configuration yaml file, and create two buttons on the dashboard. Try to copy-paste the commands, it is very easy to make a mistake in the order of single quotes, brackets, double quotes and slashes. Stuff will not work if you mistype them. 

Open up your HA terminal. This should show you a bash shell with a bunch of text and a $ sign. Welcome to Linux! If this is all new for you, you might want to read up a bit first about command lines, or you can just hope I included all needed steps in this writeup :-) Home Assistant is quite cleverly set up, with the actual homeassistant running in a virtual (docker) environment. So the shell we are in now, is not the same place as where things are executing when we use home assistant the normal way. So we first need to get into the docker environment. Run the following command to get in:

::

  docker exec -it homeassistant /bin/bash

This will change your shell to something like: “homeassistant:/config#”, indicating you are now inside the “homeassistant” docker container, in folder “/config”, as “root” user (the # symbol). Now install the modified python-eiscp package with the following command:

::

  pip install -I git+https://github.com/rlKoekie/python-eiscp.git@onkyo-groups

This should print some interesting text, and at the end there should be a line reading “Successfully installed netifaces-0.11.0 pyeiscp-0.0.7”. Feel free to ignore any warnings about running pip as ‘root’. 

**This "pip install" step will most likely have to be repeated when you update home assistant! I hope that the Onkyo plugin for home assistant itself will get the changes I made to python-eiscp integrated at some point, that will remove the need for these command line moves.**

Now we are ready to test! Let’s see if we can talk to our Onkyo devices. Run the following command, after changing the IP address (the 10.0.0.100 part) to the address of your own onkyo hardware (you wrote that down right?)

::

  eiscp_sender --host 10.0.0.100 'multiroom-status query'

This spits back some info about your Onkyo device. Write down the <deviceid>0123456DDEEFF</deviceid> somewhere (you can select it in the terminal, and then copy it with your right mouse button), repeat for your other Onkyo device(s).

Now we create the grouping command. It should look something like this:

::

  /usr/local/bin/eiscp_sender --host 10.0.0.100 'raw-message=<mgs zone="1"><groupid>1</groupid><maxdelay>500</maxdelay><devices><device id="012356AABBCC" zoneid="1"/><device id="0123456DDEEFF" zoneid="1"/></devices></mgs>'

Make sure to:

- Change the 10.0.0.100 IP address into the IP address of your main Onkyo device (the one sharing its audio to the secondary devices).
- Change 0123456DDEEFF into the mac address of the main (sending) onkyo device
- Change  012356AABBCC into the mac address of the secondary (receiving) onkyo device. (you can also setup multiroom audio with more than two devices, just repeat the <device id="012356AABBCC" zoneid="1"/> block with the mac address for another secondary onkyo device.

If you run the moddified command on the homeassistant docker shell, it should change your onkyo devices to run in flareconnect mode. Congratulations!

You can stop the audio grouping by telling the main device to switch to an empty audio group. The command should look something like this:

::

  /usr/local/bin//eiscp_sender --host 10.0.0.100 'raw-message=<mgs zone="1"><groupid>0</groupid></mgs>'

Make sure to change the IP address to your own main (sending) device IP!

If everything works: nice!

- Copy the full commands you executed to start and stop the audio grouping to a text file.
- Shut down the docker terminal by typing “exit” and hitting enter
- Shut down the home assistant terminal by again typing “exit” and hitting enter


Now use the file editor to modify your /homeassistant/configuration.yaml
Add the following section:

::

  shell_command:
    stop_flareconnect: /usr/local/bin//eiscp_sender --host 10.0.0.100 'raw-message=<mgs zone="1"><groupid>0</groupid></mgs>'
    start_flareconnect: /usr/local/bin/eiscp_sender --host 10.0.0.100 'raw-message=<mgs zone="1"><groupid>1</groupid><maxdelay>500</maxdelay><devices><device id="012356AABBCC" zoneid="1"/><device id="0123456DDEEFF" zoneid="1"/></devices></mgs>'

Of course make sure to change the start and stop commands to the ones you succesfully used in the terminal app!

After these changes to configuration.yaml, restart homeassistant (settings > system > top right menu > reboot) and wait for HA to return.

Now we are going to create the buttons on your home assistant dashboard:

- Go to settings > devices and services > select the “helpers” tab at the top
- Hit the “create helper” button on the bottom right, select “button”
- Give the button a name (e.g. “start flareconnect button”, and find a nice icon (e.g. mdi:speaker-multiple )
- Repeat to create a second button, now for “stop flareconnect button”
- Go to your home assistant dashboard, hit the “edit” button on the top right
- Select “by entities” at the top, and search for the name of your button (e.g. “flareconnect”). Select both, and proceed. Click on “add to dashboard”.

Now edit each button with the following: 

- Appearance> Give it a name, tick the “Name” box, disable the “status” box.
- Interactions> behaviour: run action (my translation might be off, my instance is in Dutch).
- Action: Shell command: start_flareconnect (or stop_flareconnect for the stop button).
- Hit “Save”. 

Select the “done editing” button on your dashboard (top right), and test your new buttons.

Problems?
---------

So your new stuff is not working? The first step is to go back to the docker command line, and try your commands again. If these work, then make sure to check for typos in the configuration.yaml file.
Now go check the home assistant log files: Settings > system > logs > 3-dot menu > Show full log. Maybe there are some hints in there. 

