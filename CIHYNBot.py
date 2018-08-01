from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler
import logging
from random import choice
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

updater = Updater(token='<TOKEN_KEY_HERE>')
dispatcher = updater.dispatcher

# connection to Firebase Database
cred = credentials.Certificate('canihaveyournumber-240e8-firebase-adminsdk-cdt0e-d7a95296fc.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://canihaveyournumber-240e8.firebaseio.com/'
})
ref = db.reference()

# for debugging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def start(bot, update):
    bot.sendMessage(chat_id=update.message.chat.id, text="Hello! Please see /help for information on how to use me.")

def help(bot, update):
	message = '''Users must set their number using /setnumber <your_number> in a private chat with me before using me in groups

	Forgotten your number? Use /whatsmynumber in a private chat to check your number

	Use the /startmeal command to start a meal session in group chats
	'''
	bot.sendMessage(chat_id=update.message.chat.id,
					text=message,
					parse_mode=ParseMode.MARKDOWN)

def set_number(bot, update, args):
	if update.message.chat.type == 'private':
		user_num = ''.join(args)
		if user_num == '':
			bot.sendMessage(chat_id=update.message.chat_id,
							text="Please follow the format e.g. /setcommand <your_number>")
		else:
			chat_id = update.message.chat.id
			user_id = update.message.from_user.id
			user_name = update.message.from_user.first_name
			ref.child('users/'+str(user_id)).update({
				'chat_id' : chat_id,
				'name' : user_name,
				'number' : user_num
			})
			bot.sendMessage(chat_id=update.message.chat_id,
							text="Your number is now " + user_num)
	else:
		bot.sendMessage(chat_id=update.message.chat_id,
						text="/setnumber command is only valid in a private chat")

def whats_my_number(bot, update):
	if update.message.chat.type == 'private':
		user_id = update.message.from_user.id
		user_num = ref.child('users/' + str(user_id)).get()['number']
		bot.sendMessage(chat_id=update.message.chat_id,
						text="Your number is " + user_num)
	else:
		bot.sendMessage(chat_id=update.message.chat_id,
						text="/whatsmynumber command is only valid in a private chat")

def start_meal(bot, update):
	new_meal = ref.child('meals').push()
	meal_id = new_meal.key
	chat_id = str(update.message.chat.id)

	start_message = "*Meal has begun!*\n\n*Givers:*\n\n*Takers:*\n"

	keyboard = [[InlineKeyboardButton("Give", callback_data='g'+meal_id+chat_id),InlineKeyboardButton("Take", callback_data='t'+meal_id+chat_id)]]
	reply_markup = InlineKeyboardMarkup(keyboard)

	bot.sendMessage(chat_id=update.message.chat_id,
					text=start_message,
					parse_mode=ParseMode.MARKDOWN,
					reply_markup=reply_markup)

def button(bot, update):
	query = update.callback_query
	action = query.data[0]
	meal_id = query.data[1:21]
	chat_id = '-' + query.data[22:] # added missing '-'
	user_id = query.from_user.id
	user_name = query.from_user.first_name

	# user has not init bot privately yet
	if ref.child('users/'+str(user_id)).get() == None:
		bot.sendMessage(chat_id=chat_id,
						text="{}, please see instructions with the /help command".format(user_name))
	else:
		ref.child('users/'+str(user_id)).update({'name': user_name}) # update user's first name in database
		messageTextChange = True

		if action == 'g':
			# if user does not exist in givers
			if ref.child('meals/'+meal_id+'/givers/'+str(user_id)).get() == None:
				# insert user and PM user to thank them
				ref.child('meals/'+meal_id+'/givers').update({user_id:1})
				bot.sendMessage(chat_id=ref.child('users/'+str(user_id)+'/chat_id').get(),
								text="Thanks for sharing your number!")
			# else remove user from givers
			else:
				ref.child('meals/'+meal_id+'/givers').update({user_id:None})
		else:
			# if no numbers yet
			if ref.child('meals/'+meal_id+'/givers').get() == None:
				bot.sendMessage(chat_id=ref.child('users/'+str(user_id)+'/chat_id').get(),
								text="Sorry, there are no available numbers at the moment.")
				messageTextChange = False
			else:
				# randomly select a number to take
				giver_selected = choice(list(ref.child('meals/'+meal_id+'/givers').get().keys()))
				num_selected = ref.child('users/'+str(giver_selected)+'/number').get()

				# delete selected from givers
				ref.child('meals/'+meal_id+'/givers/').update({giver_selected: None})

				# PM user the number
				bot.sendMessage(chat_id=ref.child('users/'+str(user_id)+'/chat_id').get(),
								text=num_selected)

				# get count of numbers taken by user
				taken_count = ref.child('meals/'+meal_id+'/takers/'+str(user_id)).get()
				
				# if user has not taken, set as 1
				if taken_count == None:
					ref.child('meals/'+meal_id+'/takers').update({user_id:1})
				# else increment count
				else:
					ref.child('meals/'+meal_id+'/takers').update({user_id:taken_count+1})

		if messageTextChange:
			givers = ref.child('meals/'+meal_id+'/givers').get()
			takers = ref.child('meals/'+meal_id+'/takers').get()
			givers_text = ""
			takers_text = ""
			if givers:
				for key in givers.keys():
					givers_text += ref.child('users/'+str(key)+'/name').get() + '\n'
			if takers:
				for key, value in takers.items():
					takers_text += "{} ({})\n".format(ref.child('users/'+str(key)+'/name').get(), value)

			message = "*Meal has begun!*\n\n*Givers:*\n{}\n*Takers:*\n{}".format(givers_text, takers_text)
			keyboard = [[InlineKeyboardButton("Give", callback_data='g'+meal_id),InlineKeyboardButton("Take", callback_data='t'+meal_id)]]
			reply_markup = InlineKeyboardMarkup(keyboard)
			bot.edit_message_text(text=message,
								chat_id=query.message.chat_id,
								message_id=query.message.message_id,
								parse_mode=ParseMode.MARKDOWN,
								reply_markup=reply_markup)


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

help_handler = CommandHandler('help', help)
dispatcher.add_handler(help_handler)

setnumber_handler = CommandHandler('setnumber', set_number, pass_args=True)
dispatcher.add_handler(setnumber_handler)

whatsmynumber_handler = CommandHandler('whatsmynumber', whats_my_number)
dispatcher.add_handler(whatsmynumber_handler)

startmeal_handler = CommandHandler('startmeal', start_meal)
dispatcher.add_handler(startmeal_handler)

dispatcher.add_handler(CallbackQueryHandler(button))

updater.start_polling()