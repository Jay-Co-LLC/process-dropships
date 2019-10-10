import datetime
import logging
import config as cfg
import taw

log_file = f"LOG-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
logger = logging.getLogger('process-dropships')
logger.setLevel(logging.INFO)
logger.addHandler(logging.FileHandler(log_file))
logger.addHandler(logging.StreamHandler())


def submit_dropships():
    taw.submit_dropships()


def get_tracking():
    taw.get_tracking()


# Sets credentials in config based on 'test' flag
cfg.setup_env()

inp = ''

while inp.lower() != 'q':
    if cfg.test:
        print("\n\r*** TEST MODE ***")
    else:
        print("\n\r!!! LIVE MODE !!!")
    print("What would you like to do?\n\r")
    print("\t1 Submit 'Dropship Ready' orders to TAW")
    print("\t2 Get tracking info from TAW for 'Awaiting Tracking' orders")
    print("\t3 Both")
    print("\t4 Switch between LIVE and TEST modes")
    print("\tq Quit\n\r")

    while True:
        print("=> ", end='')
        inp = input()

        if inp.lower() == 'q':
            exit()

        if inp == '4':
            cfg.switch_modes()

        if inp in ['1', '3']:
            submit_dropships()

        if inp in ['2', '3']:
            get_tracking()

        if inp in ['1', '2', '3', '4']:
            inp = ''
            break
