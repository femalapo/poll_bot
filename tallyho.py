import discord
from discord.ext import tasks
import datetime as dt
import sys

### Script Initialization ###

BOT_CONFIG_FILE="bot_config.txt"    # bot config file path
POLL_CONFIG_FILE="poll_config.txt"  # poll config file path

# variables initialized in read_config()
TOKEN=None                  # bot token
CHANNELS_POST=None          # channels to post poll in
CHANNELS_RESULTS=None       # channels to post poll results in
POLL_DURATION= None         # poll duration
POLL_QUESTION=None          # poll question
POLL_ANSWERS=None           # poll answers
NEEDED_FOR_PRACTICE=None    # number of positive votes needed for practice
SEND_POLL_TIME=None         # Time to send poll in HH:MM format

running_polls=[]            # persistent list of running polls

# Assign global variables for the discord bot to use
def read_configs():
    global TOKEN, CHANNELS_POST, CHANNELS_RESULTS
    global POLL_DURATION, POLL_QUESTION, POLL_ANSWERS, NEEDED_FOR_PRACTICE, SEND_POLL_TIME

    # -- Bot config format --
    # Bot Token:
    # <bot_token>
    # Channels to post poll:
    # <channel_post_1>
    # ...
    # <channel_post_n>
    #
    # Channels to post results:
    # <channel_results_1>
    # ...
    # <channel_results_n>
    with open(BOT_CONFIG_FILE, "r") as f:
        f.readline()
        TOKEN = f.readline()[:-1]

        ## CHANNELS_POST
        # Consume buffer
        while(not f.readline().startswith("Channels")):
            pass

        CHANNELS_POST = []
        while(not (line := f.readline()).startswith("Channels")):
            if line != "\n":
                CHANNELS_POST.append(int(line))

        ## CHANNELS_RESULTS
        CHANNELS_RESULTS = []
        while((line := f.readline()) != ""):
            CHANNELS_RESULTS.append(int(line))

    # -- Poll config format --
    # When to send poll (HH:MM - leave blank for immediately):
    # <HH:MM>
    #
    # Duration (in hours):
    # <duration>
    #
    # Needed for practice:
    # <needed_for_practice>
    #
    # Question:
    # <question_input>
    #
    # Answers (- denotes for no practice):
    # <answer_input_1>
    # ...
    # <answer_input_n>
    with open(POLL_CONFIG_FILE, "r") as f:
        ## SEND_POLL_TIME
        f.readline()
        t = f.readline()
        SEND_POLL_TIME = t[:-1] if t != "\n" else None

        ## POLL_DURATION
        # Consume buffer
        while(not f.readline().startswith("Duration")):
            pass

        POLL_DURATION = int(f.readline())

        ## NEEDED_FOR_PRACTICE
        # Consume buffer
        while(not f.readline().startswith("Needed for practice:")):
            pass

        NEEDED_FOR_PRACTICE = int(f.readline())

        ## POLL_QUESTION
        # Consume buffer
        while(not f.readline().startswith("Question")):
            pass

        POLL_QUESTION = f.readline()[:-1]

        ## POLL_ANSWERS
        # Consume buffer
        while(not f.readline().startswith("Answers")):
            pass

        POLL_ANSWERS = []
        while((answer := f.readline()) != ""):
            if answer[-1] == "\n":
                answer = answer[:-1]
            
            POLL_ANSWERS.append(answer)


### TallyHo Initialization ###

TallyHo_intents = discord.Intents.default()
TallyHo_intents.message_content = True

TallyHo = discord.Client(intents=TallyHo_intents)

### TallyHo Methods ###

# Check if the member in the channel is an admistrator
def check_admin(member, channel):
    return channel.permissions_for(member).administrator

# Send a poll given the configurations
async def send_poll():
    poll = discord.Poll(POLL_QUESTION, dt.timedelta(hours=POLL_DURATION))

    for answer in POLL_ANSWERS:
        t = answer
        if t.startswith("-"):
            t = t[1:]

        poll.add_answer(text=t)

    for channel in CHANNELS_POST:
        running_polls.append(
            await TallyHo.get_channel(channel).send("@everyone", poll=poll)
            )
        
# Get a string representing the status of the poll
async def get_poll_status():
    votes, practice_votes = await get_unique_votes()
    num_practice_votes = len(practice_votes)
    
    m = "We currently have:\n"
    for key in votes:
        m += f"{len(votes[key])} votes for {key}\n"

    m += f"\nThere are {num_practice_votes} votes for practice\n"

    if num_practice_votes < NEEDED_FOR_PRACTICE:
        m += "There's not enough for practice. Not poggies... :sob:"
    else:
        m += "Big Poggies! There's enough for practice!"

    return m


# Get unique votes for each answer
# Get votes for positive practice
async def get_unique_votes():
    # Initialize dictionary
    votes = {}
    practice_votes = set()

    for answer in running_polls[0].poll.answers:
        votes[answer.text] = set()

    # Get votes
    for message in running_polls:
        for answer in message.poll.answers:
            async for voter in answer.voters():
                votes[answer.text].add(voter)

                # If answer means positive practice vote
                if not f"-{answer}" in POLL_ANSWERS:
                    practice_votes.add(voter)

    return votes, practice_votes



### TallyHo Events ###

@TallyHo.event
async def on_ready():
    '''
    print(TOKEN)
    print(CHANNELS_POST)
    print(POLL_DURATION)
    print(NEEDED_FOR_PRACTICE)
    print(POLL_QUESTION)
    print(POLL_ANSWERS)
    '''

    if SEND_POLL_TIME != None:
        print(f"Poll set to send at {SEND_POLL_TIME}")
        if not send_poll_wrapper.is_running():
            send_poll_wrapper.start()
    else:
        print("Poll sending immediately.")
        await send_poll()

    if not send_result_wrapper.is_running():
        send_result_wrapper.start()
    

@TallyHo.event
async def on_message(message):
    author = message.author
    channel = message.channel

    if author == TallyHo.user:
        return
    
    if message.content.startswith('$hello'):
        await channel.send("Hello!")

    if message.content == "$poll" and check_admin(author, channel):
        if(len(running_polls) == 0):
            await channel.send("No polls are currently running")
            await channel.send("dummy")
        else:
            await channel.send(await get_poll_status())



### Main ###
if __name__ == "__main__":
    read_configs()

    send_time = dt.datetime.now(tz=dt.timezone(-dt.timedelta(hours=7)))

    ### TallyHo Tasks ###
    # Send poll
    if SEND_POLL_TIME is not None:
        send_time = dt.time(hour=int(SEND_POLL_TIME[:2]),
                            minute=int(SEND_POLL_TIME[3:]),
                            tzinfo=dt.timezone(-dt.timedelta(hours=7)))

        @tasks.loop(time=send_time)
        async def send_poll_wrapper():
            await send_poll()
            print("Poll sent.")
            send_poll_wrapper.stop()

    # Send result
    result_time = ((send_time + dt.timedelta(hours=POLL_DURATION))
                        .time()
                        .replace(tzinfo=dt.timezone(-dt.timedelta(hours=7))))
    @tasks.loop(time=result_time)
    async def send_result_wrapper():
        m = await get_poll_status()

        for channel in CHANNELS_RESULTS:
            await TallyHo.get_channel(channel).send(m)

        print("Final results sent")
        await TallyHo.close()


    ### Run TallyHo ###
    TallyHo.run(TOKEN)