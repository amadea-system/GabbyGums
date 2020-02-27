# Gabby Gums

Gabby Gums is discord logging bot that is able to ignore all the extraneous deletes that PluralKit causes from proxied messages.

## Functionality
Logs the following:
* Message Edits
* Message Deletes
  * Logs for deleted webhook messages from PK also include the Discord account that sent the original message, the System ID, and the Member ID    
  * Supports image logging if you self host Gabby Gums
* Members joining
  * Includes support for invite tracking so you can tell which invite link a person used and who created the invite.
  * Invite links can be assigned names for easier identification of invite links.
* Members leaving
* Members changing their nickname  
* Account name changes
* Account Avatar changes
* Bans, Unbans, and Kicks
  * Including the person who did the Banning/Unbanning/Kicking
* Bulk Message Deletes
  * Bulk Message Delete Logs are generated as a HTML Web Page to give an easy to visualize, Discord like view of the deleted messages that supports shows not just the message content, but Reactions and Embeds just how they looked on discord. Additionally System IDs, and Member IDs are included for PK posts.
  * These logs can also be generated using the g!archive command. 
* Channel Creation
* Channel Deletion
* Channel Edits
  * Currently supports all changes except moving channels and determining the person responsible (These will be coming very soon however).
* Able to warn you (and soon auto-ban) when a user joins that is linked to a Plural Kit Account that has previously been banned from your server. 

All of the different logged events are able to have their own log channels or be disabled entirely.  
Able to ignore events based on Channel, Category, and/or user.


## Support Server
Please join the Gabby Gums support discord server if you have any problems or wish to add Gabby Gums to your server.
https://discord.gg/Xwhk89T

## How to add Gabby Gums to your server
You can get the invite link for the main instance that I host at the support server linked above.  
If you are having problems self hosting Gabby Gums, please join the support server and ask for assistance. Eventually there will instructions included here for configureing and running the bot yourself.
