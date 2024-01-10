import os
import json
import re
import string

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

class TextColors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"

openai_api_key=os.getenv("OPENAI_API_KEY")
rolling = 10
system_message="""
Your role is to be a helpful assistant with a friendly, understanding, patient, and user-affirming tone.
You need to support the user in configuring network system devices according to the information provided.
You need to use the functions provided in order to understand which are the parameters needed for the configuration.
Use the following additional [context] below (if present) to retrieve information; 
if you cannot retrieve any information from the [context] use your knowledge.
[context] {context}"
"""

system_message_final="""
Your role is to be a network assistant that needs to generate the CISCO script 
based on the information provided by the user.
When the user asks to generate the CISCO script, 
you must only provide the list of those commands as response without any introduction or comment.
Use the following additional [context] below (if present) to retrieve information; 
if you cannot retrieve any information from the [context] use your knowledge.
[context] {context}"
"""


functions=[
    {
        "name": "dchp_server_configuration",
        "description": "This function is used to configure a DHCP server; when the user asks for the DHCP server configuration, it gets the parameters provided by the user and fill them into the properties",
        "definition": "DHCP",
        "parameters": {
            "type": "object",
            "properties": {
                "server_ip_address": {
                    "type": "string",
                    "description": "The IP of the server, e.g. 192.168.1.1 /24",
                },
                "gateway_ip_address": {
                    "type": "string",
                    "description": "The IP of the gateway, e.g. 192.168.1.254 /24",
                },
                "numhosts": {
                    "type": "integer",
                    "description": "Number of hosts that the DHCP server can handle, e.g. 100",
                },
                "start_ip_address": {
                    "type": "string",
                    "description": "Starting IP adress that can be configured, e.g. 192.168.1.1",
                },
                "escluded_ip_addresses": {
                    "type": "string",
                    "description": "Range of IPs that have to be excluded by the DHCP server, e.g. 192.168.1.100-192.168.1.150",
                },
                "pool_name": {
                    "type": "string",
                    "description": "Name of the DHCP pool to be configured, e.g. MY_POOL_NAME",
                },
                "dns_server": {
                    "type": "string",
                    "description": "The IP of the DNS server, e.g. 192.168.1.100 /24",
                },
            },
            "required": ["server_ip_address","gateway_ip_address","numhosts"],
        },
    }
]

def get_definition(functions,name):
    for func in functions:
        if func["name"] == name:
            return func["definition"]
    return None

def process_prop_description(prop_description):
    prop_description = re.sub(r'\s*e\.g\..*$', '', prop_description)
    prop_description = prop_description.rstrip(string.punctuation)
    prop_description = prop_description.strip()
    return prop_description

def set_messages(messages, rolling):
    num_entries = len(messages)
    num_couples = (num_entries - 1) // 2 

    if num_couples <= rolling:
        return messages  
        
    couples_to_remove = num_couples - rolling

    removed_couples = 0
    index = 1  
    while removed_couples < couples_to_remove:
        if messages[index]["role"] == "user" and messages[index + 1]["role"] == "assistant":
            del messages[index]
            del messages[index] 
            removed_couples += 1
        else:
            index += 1

    return messages

def find_function_by_name(functions, function_name):
    for func in functions:
        if 'name' in func and func['name'] == function_name:
            return func
    return None

def process_arguments(functions, arguments):
    result = {}
    for func in functions:
        if 'parameters' in func:
            params = func['parameters']
            if 'properties' in params:
                for prop_name, prop_info in params['properties'].items():
                    result[prop_name] = None

    if arguments:
        try:
            args_dict = json.loads(arguments)
            for arg_name, arg_value in args_dict.items():
                if arg_name in result:
                    result[arg_name] = arg_value
        except json.JSONDecodeError as e:
            print(f"Error in parsing json: {e}")

    return result

def main_loop():

    print(TextColors.RESET)

    client=OpenAI()

    messages=[]
    messages.append({"role":"system","content":system_message})

    try:
        print("\n***WELCOME***\n")
        while True:
            query = input("\nUser: ")
            messages.append({"role":"user","content":query})

            response = client.chat.completions.create(
                messages=messages,
                model='gpt-3.5-turbo-0613',
                temperature=0,
                max_tokens=400,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                functions=functions,
                function_call="auto"
            )

            print(TextColors.RED)
            print(response)
            print(TextColors.RESET)

            #check if the response contains content or not
            if response.choices[0].message.content:
                print("Assistant: "+response.choices[0].message.content)
                messages.append({"role":"assistant","content":response.choices[0].message.content})
            elif response.choices[0].message.function_call:
                function_to_process = find_function_by_name(functions, response.choices[0].message.function_call.name)
                
                # print(TextColors.GREEN)
                # print(function_to_process)
                # print(TextColors.RESET)

                if function_to_process:
                    arguments = response.choices[0].message.function_call.arguments
                    elements = process_arguments([function_to_process], arguments)

                    # print(TextColors.GREEN)
                    # print(arguments)
                    # print(elements)
                    # print(TextColors.RESET)

                    message_generated = False

                    for prop_name, prop_info in function_to_process['parameters']['properties'].items():
                        prop_value = elements[prop_name]

                        # print(TextColors.GREEN)
                        # print(prop_value)
                        # print(TextColors.RESET)
                        
                        if prop_value is None and prop_name in function_to_process['parameters']['required']:
                            prop_description = prop_info.get('description', '')
                            prop_description = prop_description[0].lower() + prop_description[1:]

                            # Generate the message
                            message = 'Please provide me with ' + prop_description
                            print("Assistant: "+message)
                            messages.append({"role":"assistant","content":message})

                            message_generated=True

                            break

                    if not message_generated:
                        # All required elements have been retrieved:
                        message="Please generate the script"
                        message=message +" for the final configuration of the "
                        message=message + get_definition(functions=functions, name=response.choices[0].message.function_call.name)
                        message=message+" based on the following parameters: "

                        for prop_name, prop_info in function_to_process['parameters']['properties'].items():
                            prop_value = elements[prop_name]
    
                            if prop_value is not None:
                                prop_description = prop_info.get('description', '')
                                prop_description = prop_description[0].lower() + prop_description[1:]
                                message=message+"\n - "+process_prop_description(prop_description)+": "+str(prop_value)+"; "

                        print(TextColors.BLUE)
                        print(message)
                        print(TextColors.RESET)

                        messages_final=[]
                        messages_final.append({"role":"system","content":system_message_final})
                        messages_final.append({"role":"user","content":message})

                        response = client.chat.completions.create(
                            messages=messages_final,
                            model='gpt-3.5-turbo-0613',
                            temperature=0,
                            max_tokens=400,
                            top_p=1,
                            frequency_penalty=0,
                            presence_penalty=0
                        )

                        print(TextColors.RED)
                        print(response)
                        print(TextColors.RESET)

                        print("Assistant: "+response.choices[0].message.content)
                        messages.append({"role":"user","content":message})
                        messages.append({"role":"assistant","content":response.choices[0].message.content})
                else:
                    wrong="something wrong occurred..."
                    print("Assistant: "+wrong)
                    messages.append({"role":"assistant","content":wrong})

            messages = set_messages(messages,rolling)
            
    except KeyboardInterrupt:
        print("BYE BYE!!!")

main_loop()



#from langchain.chat_models import ChatOpenAI
#from langchain.schema import HumanMessage, AIMessage, ChatMessage

# functions=[
#     {
#         "name": "get_parameters",
#         "description": "Get the parameters provided by the user and fill them into the properties; the goal is to configure a DHCP server",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "server_ip_address": {
#                     "type": "string",
#                     "description": "The IP of the server, e.g. 192.168.1.1 /24",
#                 },
#                 "gateway_ip_address": {
#                     "type": "string",
#                     "description": "The IP of the gateway, e.g. 192.168.1.254 /24",
#                 },
#                 "numhosts": {
#                     "type": "integer",
#                     "description": "Number of hosts that the DHCP server can handle, e.g. 100",
#                 },
#                 "start_ip_address": {
#                     "type": "string",
#                     "description": "Starting IP adress that can be configured, e.g. 192.168.1.1",
#                 },
#                 "escluded_ip_addresses": {
#                     "type": "string",
#                     "description": "Range of IPs that have to be excluded by the DHCP server, e.g. 192.168.1.100-192.168.1.150",
#                 },
#             },
#             "required": ["server_ip_address","numhosts"],
#         },
#     }
# ]

#llm=ChatOpenAI(model="gpt-3.5-turbo-0613")

# def straightforward():
#     query="I need to configure a DHCP server with IP 192.168.1.100 /24 and 100 hosts"
#     messages=[HumanMessage(content=query)]
#     assistant_reply=llm.predict_messages(
#         messages=messages,
#         functions=functions
        
#     )
#     #print(message)
#     #content='' additional_kwargs={'function_call': {'name': 'get_parameters', 'arguments': '{\n  "server_ip_address": "192.168.1.100/24",\n  "numhosts": 100\n}'}} example=False

#     # query="I need to configure a DHCP server with IP 192.168.1.100 /24 and 100 hosts; the gateway is 192.168.1.254 /24"
#     # message=llm.predict_messages(
#     #     [HumanMessage(content=query)],
#     #     functions=functions
#     # )
#     # print(message)
#     #content='' additional_kwargs={'function_call': {'name': 'get_parameters', 'arguments': '{\n  "server_ip_address": "192.168.1.100/24",\n  "gateway_ip_address": "192.168.1.254/24",\n  "numhosts": 100\n}'}} example=False

#     #additional_kwargs={'function_call': {'name': 'get_parameters', 'arguments': '{\n  "server_ip_address": "192.168.1.100/24",\n  "gateway_ip_address": "192.168.1.254/24",\n  "numhosts": 100\n}'}}

#     arguments = assistant_reply.additional_kwargs.get('function_call', {}).get('arguments', '')
#     function_name = assistant_reply.additional_kwargs.get('function_call', {}).get('name', '')
#     function_to_process = find_function_by_name(functions, function_name)

#     if function_to_process:
#         elements = process_arguments([function_to_process], arguments)

#         for prop_name, prop_value in elements.items():
#             if prop_value is None:
#                 prop_info = function_to_process['parameters']['properties'][prop_name]
#                 prop_description = prop_info.get('description', '')
#                 prop_description = prop_description[0].lower()+prop_description[1:]
                
#                 while True:
#                     message='Please provide me with '+prop_description
#                     #print(message)
#                     messages.append(AIMessage(content=message))
#                     user_response=input(message+': ')
#                     messages.append(HumanMessage(content=user_response))
                    
#                     assistant_reply=llm.predict_messages(
#                         messages=messages,
#                         functions=functions
#                     )
#                     print(assistant_reply)

#                     local_arguments = assistant_reply.additional_kwargs.get('function_call', {}).get('arguments', '')
#                     local_function_name = assistant_reply.additional_kwargs.get('function_call', {}).get('name', '')
#                     local_function_to_process = find_function_by_name(functions, local_function_name)
                    
#                     if not local_function_to_process:
#                         raise ValueError(f"Function with name '{function_name}' not found.")
                    
#                     local_elements = process_arguments([local_function_to_process], local_arguments)
#                     if local_elements[prop_name] is not None:
#                         elements[prop_name]=local_elements[prop_name]
#                         break          

#         print(result)
#     else:
#         print(f"Function with name '{function_name}' not found.")
