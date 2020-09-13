#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import pygame 
import time

from aioconsole import ainput

from joycontrol import logging_default as log, utils
from joycontrol.command_line_interface import ControllerCLI
from joycontrol.controller import Controller
from joycontrol.controller_state import ControllerState, button_push
from joycontrol.memory import FlashMemory
from joycontrol.protocol import controller_protocol_factory
from joycontrol.server import create_hid_server

logger = logging.getLogger(__name__)
pygame.joystick.init()
#pygame.display.set_mode((100,100))

pygame.init()

"""Emulates Switch controller. Opens joycontrol.command_line_interface to send button commands and more.

While running the cli, call "help" for an explanation of available commands.

Usage:
    run_controller_cli.py <controller> [--device_id | -d  <bluetooth_adapter_id>]
                                       [--spi_flash <spi_flash_memory_file>]
                                       [--reconnect_bt_addr | -r <console_bluetooth_address>]
                                       [--log | -l <communication_log_file>]
                                       [--nfc <nfc_data_file>]
    run_controller_cli.py -h | --help

Arguments:
    controller      Choose which controller to emulate. Either "JOYCON_R", "JOYCON_L" or "PRO_CONTROLLER"

Options:
    -d --device_id <bluetooth_adapter_id>   ID of the bluetooth adapter. Integer matching the digit in the hci* notation
                                            (e.g. hci0, hci1, ...) or Bluetooth mac address of the adapter in string
                                            notation (e.g. "FF:FF:FF:FF:FF:FF").
                                            Note: Selection of adapters may not work if the bluez "input" plugin is
                                            enabled.

    --spi_flash <spi_flash_memory_file>     Memory dump of a real Switch controller. Required for joystick emulation.
                                            Allows displaying of JoyCon colors.
                                            Memory dumps can be created using the dump_spi_flash.py script.

    -r --reconnect_bt_addr <console_bluetooth_address>  Previously connected Switch console Bluetooth address in string
                                                        notation (e.g. "FF:FF:FF:FF:FF:FF") for reconnection.
                                                        Does not require the "Change Grip/Order" menu to be opened,

    -l --log <communication_log_file>       Write hid communication (input reports and output reports) to a file.

    --nfc <nfc_data_file>                   Sets the nfc data of the controller to a given nfc dump upon initial
                                            connection.
"""

async def _main(args):
    # parse the spi flash
    if args.spi_flash:
        with open(args.spi_flash, 'rb') as spi_flash_file:
            spi_flash = FlashMemory(spi_flash_file.read())
    else:
        # Create memory containing default controller stick calibration
        spi_flash = FlashMemory()

    # Get controller name to emulate from arguments
    controller = Controller.from_arg(args.controller)

    with utils.get_output(path=args.log, default=None) as capture_file:
        factory = controller_protocol_factory(controller, spi_flash=spi_flash)
        ctl_psm, itr_psm = 17, 19
        transport, protocol = await create_hid_server(factory, reconnect_bt_addr=args.reconnect_bt_addr,
                                                      ctl_psm=ctl_psm,
                                                      itr_psm=itr_psm, capture_file=capture_file,
                                                      device_id=args.device_id)

        controller_state = protocol.get_controller_state()

        # Create command line interface and add some extra commands
        cli = ControllerCLI(controller_state)

        # Wrap the script so we can pass the controller state. The doc string will be printed when calling 'help'

        async def _run_Controller():
            '''
            - Controller
            '''
            await xbox(controller_state)
        

        # add the script from above
        #cli.add_command('mash', call_mash_button)
        cli.add_command('Controller', _run_Controller)

       

        try:
            await cli.run()
        finally:
            logger.info('Stopping communication...')
            await transport.close()


async def xbox(controller_state: ControllerState):# this method binds keyboard to controller for CLI keyboard control of switch
    if controller_state.get_controller() != Controller.PRO_CONTROLLER:
        raise ValueError('This script only works with the Pro Controller!')
    # waits until controller is fully connected
    await controller_state.connect()

    
    lv = 0
    lh = 0
    rv = 0
    rh = 0
    #button state handler callbacks

    Working = True
    start_time = time.time()
    while Working:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    Working = False
                    break
            if event.type == pygame.USEREVENT:
                pygame.time.set_timer(pygame.USEREVENT, 0)
                Working = False
                break
                
        LeftStick = controller_state.l_stick_state
        RightStick = controller_state.r_stick_state

        
        joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]
        for i in range(pygame.joystick.get_count()):
            joysticks[i].init()
      
        for i in range(pygame.joystick.get_count()):
            #Left Stick
            
            if round(lh,-1) != round(2048 + joysticks[i].get_axis(0)*1792,-1) or round(lv,-1) != round(2048 + joysticks[i].get_axis(1)*1792,-1):
                lh = (2048 + joysticks[i].get_axis(0)*1792)
                lv = (2048 - joysticks[i].get_axis(1)*1792)

                if lh < 2150 and lh > 1950:
                    lh = 2048
                if lv < 2150 and lv > 1950:
                    lv = 2048
                
                ControllerCLI._set_stick(LeftStick, 'h', lh)
                ControllerCLI._set_stick(LeftStick, 'v', lv)
        
                

            #Right Stick 
            if round(rh,-1) != round(2048 + joysticks[i].get_axis(3)*1792,-1) or round(rv,-1) != round(2048 + joysticks[i].get_axis(4)*1792,-1):
                rh = (2048 + joysticks[i].get_axis(3)*1792)
                rv = (2048 - joysticks[i].get_axis(4)*1792)

                if rh < 2150 and rh > 1950:
                    rh = 2048
                if rv < 2150 and rv > 1950:
                    rv = 2048
                    
                ControllerCLI._set_stick(RightStick, 'h', rh)
                ControllerCLI._set_stick(RightStick, 'v', rv)
                


            #Triggers
            if joysticks[i].get_axis(2) >= 0.2:
                controller_state.button_state.set_button('zl')
            else:
                controller_state.button_state.set_button('zl', pushed=False)

            if joysticks[i].get_axis(5) >= -0.2:
                controller_state.button_state.set_button('zr')
            else:
                controller_state.button_state.set_button('zr', pushed=False)



            #Buttons

            if joysticks[i].get_button(0) == 1: #B
                controller_state.button_state.set_button('b')
            else:
                controller_state.button_state.set_button('b', pushed=False)

            if joysticks[i].get_button(1) == 1: #A
                controller_state.button_state.set_button('a')
            else:
                controller_state.button_state.set_button('a', pushed=False)

            if joysticks[i].get_button(2) == 1: #Y
                controller_state.button_state.set_button('y')
            else:
                controller_state.button_state.set_button('y', pushed=False)

            if joysticks[i].get_button(3) == 1: #X
                controller_state.button_state.set_button('x')
            else:
                controller_state.button_state.set_button('x', pushed=False)

            #Trigger Buttons
            if joysticks[i].get_button(4) == 1: #Left
                controller_state.button_state.set_button('l')
            else:
                controller_state.button_state.set_button('l', pushed=False)

            if joysticks[i].get_button(5) == 1: #Right
                controller_state.button_state.set_button('r')
            else:
                controller_state.button_state.set_button('r', pushed=False)

            #Other Buttons

            if joysticks[i].get_button(6) == 1: #Minius
                controller_state.button_state.set_button('minus')
            else:
                controller_state.button_state.set_button('minus', pushed=False)
                
            if joysticks[i].get_button(7) == 1: #plus
                controller_state.button_state.set_button('plus')
            else:
                controller_state.button_state.set_button('plus', pushed=False)
                
                

            #Dpad
            hat = joysticks[i].get_hat( 0 )
            if hat[0] == 1: #Right
                controller_state.button_state.set_button('right')
            else:
                controller_state.button_state.set_button('right', pushed=False)

            if hat[0] == -1: #Left
                controller_state.button_state.set_button('left')
            else:
                controller_state.button_state.set_button('left', pushed=False)
                
            if hat[1] == 1: #Up
                controller_state.button_state.set_button('up')
            else:
                controller_state.button_state.set_button('up', pushed=False)

            if hat[1] == -1: #Down
                controller_state.button_state.set_button('down')
            else:
                controller_state.button_state.set_button('down', pushed=False)
                
            await controller_state.send()



if __name__ == '__main__':
    # check if root
    if not os.geteuid() == 0:
        raise PermissionError('Script must be run as root!')

    # setup logging
    #log.configure(console_level=logging.ERROR)
    log.configure()

    parser = argparse.ArgumentParser()
    parser.add_argument('controller', help='JOYCON_R, JOYCON_L or PRO_CONTROLLER')
    parser.add_argument('-l', '--log')
    parser.add_argument('-d', '--device_id')
    parser.add_argument('--spi_flash')
    parser.add_argument('-r', '--reconnect_bt_addr', type=str, default=None,
                        help='The Switch console Bluetooth address, for reconnecting as an already paired controller')
    parser.add_argument('--nfc', type=str, default=None)
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        _main(args)
    )
