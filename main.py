import os
import json

from dotenv import load_dotenv
load_dotenv()

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, ChatMessage


openai_api_key=os.getenv("OPENAI_API_KEY")

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

functions=[
    {
        "name": "get_parameters",
        "description": "Get the parameters provided by the user and fill them into the properties; the goal is to configure a DHCP server",
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
            },
            "required": ["server_ip_address","numhosts"],
        },
    }
]

llm=ChatOpenAI(model="gpt-3.5-turbo-0613")

query="I need to configure a DHCP server with IP 192.168.1.100 /24 and 100 hosts"
messages=[HumanMessage(content=query)]
assistant_reply=llm.predict_messages(
    messages=messages,
    functions=functions
)
#print(message)
#content='' additional_kwargs={'function_call': {'name': 'get_parameters', 'arguments': '{\n  "server_ip_address": "192.168.1.100/24",\n  "numhosts": 100\n}'}} example=False

# query="I need to configure a DHCP server with IP 192.168.1.100 /24 and 100 hosts; the gateway is 192.168.1.254 /24"
# message=llm.predict_messages(
#     [HumanMessage(content=query)],
#     functions=functions
# )
# print(message)
#content='' additional_kwargs={'function_call': {'name': 'get_parameters', 'arguments': '{\n  "server_ip_address": "192.168.1.100/24",\n  "gateway_ip_address": "192.168.1.254/24",\n  "numhosts": 100\n}'}} example=False

#additional_kwargs={'function_call': {'name': 'get_parameters', 'arguments': '{\n  "server_ip_address": "192.168.1.100/24",\n  "gateway_ip_address": "192.168.1.254/24",\n  "numhosts": 100\n}'}}

arguments = assistant_reply.additional_kwargs.get('function_call', {}).get('arguments', '')
function_name = assistant_reply.additional_kwargs.get('function_call', {}).get('name', '')
function_to_process = find_function_by_name(functions, function_name)

if function_to_process:
    elements = process_arguments([function_to_process], arguments)

    for prop_name, prop_value in elements.items():
        if prop_value is None:
            prop_info = function_to_process['parameters']['properties'][prop_name]
            prop_description = prop_info.get('description', '')
            prop_description = prop_description[0].lower()+prop_description[1:]
            
            while True:
                message='Please provide me with '+prop_description
                #print(message)
                messages.append(AIMessage(content=message))
                user_response=input(message+': ')
                messages.append(HumanMessage(content=user_response))
                
                assistant_reply=llm.predict_messages(
                    messages=messages,
                    functions=functions
                )
                print(assistant_reply)

                local_arguments = assistant_reply.additional_kwargs.get('function_call', {}).get('arguments', '')
                local_function_name = assistant_reply.additional_kwargs.get('function_call', {}).get('name', '')
                local_function_to_process = find_function_by_name(functions, local_function_name)
                
                if not local_function_to_process:
                    raise ValueError(f"Function with name '{function_name}' not found.")
                
                local_elements = process_arguments([local_function_to_process], local_arguments)
                if local_elements[prop_name] is not None:
                    elements[prop_name]=local_elements[prop_name]
                    break          

    print(result)
else:
    print(f"Function with name '{function_name}' not found.")