from intbase import InterpreterBase, ErrorType
from brewparse import parse_program
 
# Interpreter class derived from interpreter base class
class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False):
        # call InterpreterBase's constructor
        super().__init__(console_output, inp)
        # call stack will keep track of functions using a last in first out approach, each dict keeps track of things like variables, e.g., a dict that maps variable names to their current value (e.g., { "foo" → 11 })
        self.call_stack = [] 
        # store function names (tracker for funcs) in a dictionary
        self.func_name_to_ast = dict()
        # keeps track of structs
        self.struct_tracker = {}
        # keep track of structs 
        self.variable_type_tracker = {}
        
        
    # The Interpreter is passed in a program as a list of strings that needs to be interpreted
    def run(self, program):
        # parse program into AST
        ast = parse_program(program)
        # set up a function tracker that keeps track of the func names
        # set up struct tracker that keeps track of the struct names
        self.set_up_struct_tracker(ast)
        self.set_up_function_tracker(ast)
        
        # look for the main function node in AST (will throw error if no main found)
        if ("main", 0) not in self.func_name_to_ast:
            super().error(ErrorType.NAME_ERROR, "Function main not found")
        # get the main func node
        main_func_node = self.func_name_to_ast[("main", 0)]
        # call run func on main function node (remember main func has no args so we say None)
        self.run_func(main_func_node, [])
     
    # struct tracker is a dictionary that keeps track of struct names   
    def set_up_struct_tracker(self, ast):
        # loop through struct definition nodes 
        for struct_def in ast.dict['structs']:
            struct_name = struct_def.dict['name']
            # map struct name to structs node
            self.struct_tracker[struct_name] = struct_def
        
        
    # function tracker is a dictionary that keeps track of function names
    def set_up_function_tracker(self, ast):
        # loop through function Nodes
        for func_def in ast.dict['functions']:
            name = func_def.dict['name']
            # 'args' which maps to a list of Argument nodes
            number_of_params = len(func_def.dict['args'])
            
            # check that parameters are valid (if struct is a parameter it must be a struct that exists)
            for param in func_def.dict['args']:
                # check if param is a struct type
                #print(param.dict['var_type'])
                if param.dict['var_type'] != 'int' and param.dict['var_type'] != 'string' and param.dict['var_type'] != 'bool':
                    if param.dict['var_type'] not in self.struct_tracker:
                        super().error(ErrorType.TYPE_ERROR, f" Invalid type for formal parameter {param.dict['name']} in function {name}")
                 
            # chekc that the function has a valid return type       
            if func_def.dict['return_type'] != 'void' and func_def.dict['return_type'] != 'string' and func_def.dict['return_type'] != 'int' and func_def.dict['return_type'] != 'bool' and func_def.dict['return_type'] not in self.struct_tracker:
                super().error(ErrorType.TYPE_ERROR, f" Invalid return type for func {name}")

            
            # this line adds the function name and number of args as a key to func_name_to_ast dictionary (e.g. key (function name, # of params))
            self.func_name_to_ast[(name, number_of_params)] = func_def
        
        
    # find a function in function tracker by name and len of args 
    def get_func_by_name_and_param_len(self, name, args):
        if (name, args) not in self.func_name_to_ast:
            super().error(ErrorType.NAME_ERROR, f"Function {name} not found")
        return self.func_name_to_ast[(name, args)]
        
    # Execute each statement inside the main function (at this point we pass in the arg values)    
    def run_func(self, func_node, args):
        # remember at this point we have verified the function exists
        
        # new local scope for function (it keeps track of variable names with a list of dictionaries, note we add a new dictionary for every if or for loop)
        # make a dict for the variables in the func
        local_scope = dict()        
        
        # match arg nodes with the paramters
        for arg_var_node, arg_value in zip(func_node.dict['args'], args):
            # get the parameter type
            parameter_type = arg_var_node.dict['var_type']
            
            coerce = False
            if arg_value.elem_type == 'var':
                arg_value_name = arg_value.dict['name']
                # check that param type matches argument type
                if arg_value_name in self.call_stack[-1][0]:
                    # we can pass int to bool
                    if (parameter_type == 'bool' and self.call_stack[-1][0][arg_value_name]['type'] == 'int'):
                        coerce = True
                        pass
                    elif (self.call_stack[-1][0][arg_value_name]['type'] != parameter_type):
                        super().error(ErrorType.TYPE_ERROR, f"target variable and source value are incompatible")

            # coerce int to bool 
            if (coerce == True):
                evaluated_arg_value = self.int_to_bool_coercion(self.call_stack[-1][0][arg_value_name]['value'])
            else:
            # Note we can pass in an expression as an arg value (ex: -1)
                evaluated_arg_value = self.do_evaluate_expression(arg_value)
            

            # check that arguments passed match the parameter types
            if self.is_type_compatible(parameter_type, evaluated_arg_value) == False:
                super().error(ErrorType.TYPE_ERROR, f"target variable and source value are incompatible")
            
            # passing an integer value/variable to a function that has a boolean formal parameter  
            if parameter_type == 'bool' and isinstance(evaluated_arg_value, int):
                evaluated_arg_value = self.int_to_bool_coercion(evaluated_arg_value)
            
            # match parameter name with argument value and type
            local_scope[arg_var_node.dict['name']] = {
                'value': evaluated_arg_value,
                'type': parameter_type
            }
        
        # call_stack is our global variable that keeps track of function scopes
        # We push the functions local_scope onto the stack
        self.call_stack.append([local_scope])
        
        # Execute each statement inside the function
        for statement in func_node.dict['statements']:
            # result is the return statment
            
            # check if struct return type matches the returned struct type
            if (statement.elem_type == 'return'):
                if (statement.dict['expression'] != None):
                    #print("EXPRESSION", statement.dict['expression'])
                    if (statement.dict['expression'].elem_type == 'var'):
                        arg_value_name = statement.dict['expression'].dict['name']
                        if arg_value_name in self.call_stack[-1][0]:
                            if self.call_stack[-1][0][arg_value_name]['type'] in self.struct_tracker:
                               if self.call_stack[-1][0][arg_value_name]['type'] != func_node.dict['return_type']:
                                super().error(ErrorType.TYPE_ERROR, f"target variable and source value are incompatible")
             
            # check if we return nil from primitive
            if (statement.elem_type == 'return'):
                if (statement.dict['expression'] != None):
                    if statement.dict['expression'].elem_type == 'nil':
                    #if statement.dict['expression'] ==
                        #print(func_node.dict['return_type'])
                        if func_node.dict['return_type'] == 'string' or func_node.dict['return_type'] == 'int' or func_node.dict['return_type'] == 'bool' or func_node.dict['return_type'] == 'void':
                            super().error(ErrorType.TYPE_ERROR, f"cant return nil for primitive return type")
                
            
            result = self.run_statement(statement)
            
            if(func_node.dict['return_type'] == 'void') and result != None:
                super().error(ErrorType.TYPE_ERROR, f"cant return value from void func")
                
                
            # note a function can return nil so its techincally returning something (ex: return nil; or return;)
            if (result == "nil"):
                return None
            
                
            # we have a return statement in the function
            if (result != None):
                # note return has handled popping from stack so need for popping here       
                return_type_of_func = func_node.dict['return_type']
                # print(return_type_of_func)
                # print("result", result)
                if (self.is_type_compatible(return_type_of_func, result)) == False:
                    super().error(ErrorType.TYPE_ERROR, f"return type and return value are incompatible")
                    
                # returning an integer value/variable from a function that has a boolean return type
                if return_type_of_func == 'bool' and isinstance(result, int):
                    result = self.int_to_bool_coercion(result)
                
                return result
            
        # the function does not have a return statement, return the default value for the function's return type upon the function's completion
        return_type = func_node.dict['return_type']
        
        #print(return_type)
        
        # return type maps to a string holding the return type of the function
        if (return_type == 'int'):
            default_value = 0
        elif (return_type == 'bool'):
            default_value = False
        elif (return_type == 'string'):
            default_value = ""
        # we have a user defined structure
        else:
            # we have a user defined structure to return
            #else: 
            default_value = None
        
        
        # we dont have something to return (so we just pop scope)
        self.call_stack.pop()
        return default_value
    
    # process different kind of statements     
    def run_statement(self, statement_node):
        # is_definition
        if statement_node.elem_type == 'vardef':
            self.do_definition(statement_node)
        # is_assignment
        elif statement_node.elem_type == '=':
            self.do_assignment(statement_node)
        # is_func_call (note only print can be found in the statement node not print)
        elif statement_node.elem_type == 'fcall':
            self.do_func_call(statement_node)
        # is if statement
        elif statement_node.elem_type == 'if':
            # there can be a return in the if statement
            return self.do_if_statement(statement_node)
        # is for loop
        elif statement_node.elem_type == 'for':
            # there can be a return in the for loop
            return self.do_for_loop(statement_node)
        # is a return statement
        elif statement_node.elem_type == 'return':
            return self.do_return_statement(statement_node)
    
    
    def do_return_statement(self, statement_node):
        # get the expression
        expression = statement_node.dict['expression'] 
        
        # first check if the return value is None (ex: return;)
        if expression == None:
            #expression = "return with no value"
            return None
        
        # 'expression' which maps to an expression, variable or constant to return or None (if the return statement returns a default value of nil)
        # do_evaluate expression will handle the cases above
        evaluated_expression = self.do_evaluate_expression(expression)
        
        # this means we had a 'return nil;' SO we techincally return something
        if evaluated_expression == None:
            return None
        
        # pop the whole scope we are in when we encounter return
        self.call_stack.pop()
        return evaluated_expression
    
     
    def do_for_loop(self, statement_node):
        # handle the assignment
        self.do_assignment(statement_node.dict['init'])
            
        while True:
            # if the condition is true so we run the statements inside the for loop
            # we are in the for loop so now can can add its scope to stack
            local_scope = dict()
            self.current_scope().append(local_scope)
            # check if the condition of the for loop does not evaluate to a boolean
            is_condition = self.do_evaluate_expression(statement_node.dict['condition'])
            
            #using an integer value/variable as the condition for a for statement e.g., for (k = 5; k ; k = k - 1)
            if type(is_condition) == int:
                is_condition = self.int_to_bool_coercion(is_condition)
            
            if isinstance(is_condition, bool) == False:
                            super().error(
                        ErrorType.TYPE_ERROR,
                        "condition of the for loop does not evaluate to a boolean",
                    )
            # we have finished exceuting the for loop so we can pop its scope from the stack
            elif is_condition == False:
                self.current_scope().pop()
                return
            
            # conditon is true so we run statements inside for loop
            for statement in statement_node.dict['statements']:
                result = self.run_statement(statement)
                if (result != None):
                    return result
                
            # pop the dictonary (local_scope) of the for loop iteration
            self.current_scope().pop()
            # update the condition and check if its true
            self.do_assignment(statement_node.dict['update'])
        
        
    def do_if_statement(self, statement_node):
        # the expression/variable/value that is the condition of the if statement must evaluate to a boolean
        is_it_bool = self.do_evaluate_expression(statement_node.dict['condition'])
        
        # using an integer value/variable as the condition for an if statement: if (some_int_variable) { /* do this */ }
        if type(is_it_bool) == int:
            is_it_bool = self.int_to_bool_coercion(is_it_bool)
        
        if isinstance(is_it_bool, bool) == False:
            super().error(
                    ErrorType.TYPE_ERROR,
                    "condition of the if statement does not evaluate to a boolean",
                )
            
        # condition maps to a boolean expression, variable or constant that must be True for the if statement to be executed
        if (is_it_bool == True):
            # we need a new scope for if statement
            local_scope = dict() 
            self.current_scope().append(local_scope)
            # eun statemnts in if statement
            for statement in statement_node.dict['statements']:
                # result is the return statment (in case we have return in if statement)
                
                print(statement)
                
                result = self.run_statement(statement)
                # if the return statement inside the if statment did return with no return value (ex: return;)
                if result == "return with no value":
                    self.call_stack.pop()
                    return "nil"
                
                if (result != None):
                # we have finished executing function so we can return (return handles the popping offf the stack)
                    return result
                
            # delete the if statement scope from list of dictionaries
            self.current_scope().pop()
        
        # condition in if statement is false  
        else:
            # There is no else clause
            if statement_node.dict['else_statements'] is None:
                # we continue running the rest of the statements otuside if clause (we dont need to pop in this case as the if clause was false so we never created a scope for the if clause)
                return
            # we have an else clause
            else:
                # we need a scope for brackets in else clause
                local_scope = dict()
                self.current_scope().append(local_scope)
                # run statements in else clause
                for statement in statement_node.dict['else_statements']:
                    result = self.run_statement(statement)
                    if (result != None):
                        return result
                # pop else scope
                self.current_scope().pop()
            
    # Add variable name to variable_tracker if possible (can't redefine it)
    def do_definition(self, statement_node):
        # check that the varibale is not already defined in the current scope which is the current dictionary we are in
        if statement_node.dict['name'] in self.current_scope()[-1]:
            super().error(
                ErrorType.NAME_ERROR,
                f"variable {statement_node.dict['name']} defined more than once",
            )
        else:
            variable_type = statement_node.dict['var_type']
            
            # intialize the variable with its default value
            if (variable_type == 'int'):
                default_value = 0
            elif (variable_type == 'bool'):
                default_value = False
            elif (variable_type == 'string'):
                default_value = ""
            # we have a user defined structure
            else:
                # check that the type exists (check if its in struct tracker
                if (variable_type not in self.struct_tracker):
                    super().error(
                    ErrorType.TYPE_ERROR,
                    "Variable type was not found",
                )
                # user defined structure should be nil 
                default_value = None
                
            # add the variable def to the last dictionary in list of dictionaries (name as key and value as a dictionary with 'value' and 'type' as keys) (this is dictionary of dictionaries logic)
            self.current_scope()[-1][statement_node.dict['name']] = {
                'value' : default_value,
                'type' : variable_type
            }
            # will help with checking if argument matches paramter type
            self.variable_type_tracker[statement_node.dict['name']] = {
                'value' : default_value,
                'type' : variable_type
            }
    
    # assign value to variable     
    def do_assignment(self, statement_node):
        # get the name of the variable (ex: 'x')
        variable_name = statement_node.dict['name']
        
        # simple case for when we have one key and one field
        if "." in variable_name:
            split_var_name = variable_name.split(".")
            if len(split_var_name) == 2:
                # top level field
                struct_name = split_var_name[0]
                struct_field = split_var_name[1]
                # verify that struct name is in scope
                in_scope = False
                dictionary_scope = None
                struct_instance = None

                for dict_scope in reversed(self.current_scope()):
                    if struct_name in dict_scope:
                        # we save the dictionary where this struct name is located
                        dictionary_scope = dict_scope
                        in_scope = True
                        struct_instance = dict_scope[struct_name]
                        # as soon as we find the first dict that has this variable we break
                        break
                    
                # variable name not in scope
                if in_scope == False:
                    super().error(
                        ErrorType.NAME_ERROR,
                        f"Variable {variable_name} has not been defined",
                    )
                # If, during execution, the variable to the left of a dot is nil, then you must generate an error of ErrorType.FAULT_ERROR.
                if struct_instance['value'] == None:
                    super().error(ErrorType.FAULT_ERROR,f"variable to the left of dot is nil",
                    )
                # If, during execution, the variable to the left of a dot is not a struct type, then you must generate an error of ErrorType.TYPE_ERROR.
                if struct_instance['type'] not in self.struct_tracker:
                    super().error(ErrorType.TYPE_ERROR, "struct to left of dot is not a struct type",
                    )
                # If, during execution, a field name is invalid (e.g., it's not a valid field in a struct definition), then you must generate an error of ErrorType.NAME_ERROR.
                struct_instance_type = struct_instance['type']
                struct_def = self.struct_tracker[struct_instance_type]
                does_field_exist = False
                for field in struct_def.dict['fields']:
                    if field.dict['name'] == struct_field:
                        field_type_expected = field.dict['var_type']
                        does_field_exist = True
                        break
                # field does not exist
                if does_field_exist == False:
                    super().error(ErrorType.NAME_ERROR, f"Field to right of dot does not exist",)


                # get expression node (the value being assigned to variable)
                expression = statement_node.dict['expression']
                # call do_evaulate_expression which handles the expression (ex: x = 5 + 6;)
                resulting_value = self.do_evaluate_expression(expression)
                # check if field type and value are compatible
                if self.is_type_compatible(field_type_expected, resulting_value) == False:
                #If the types of the target variable and source value are incompatible, you must generate an error
                    super().error(ErrorType.TYPE_ERROR, f"field type and value are incompatible")

                # assign field to value (field is not a struct)
                if type(resulting_value) == int or type(resulting_value) == str or type(resulting_value) == bool:
                    # assigning an int to bool field
                    if type(struct_instance['value'][struct_field]['value']) == bool and type(resulting_value) == int:
                        bool_resulting_value = self.int_to_bool_coercion(resulting_value)
                        struct_instance['value'][struct_field]['value'] = bool_resulting_value
                        return 
                
                struct_instance['value'][struct_field]['value'] = resulting_value
                return
                
        #### case where we have multiple fields ##########
        
        # check if variable has the dot operator
        if "." in variable_name:
            split_var_name = variable_name.split(".")
            # top level field
            struct_name = split_var_name[0]
            
            # handle case where top level is not a struct
            if struct_name in self.call_stack[-1][0]:
                # top level type not found
                if self.call_stack[-1][0][struct_name]['type'] not in self.struct_tracker:
                    super().error(ErrorType.TYPE_ERROR, f"dot used with non struct")
                # top level is None
                if self.call_stack[-1][0][struct_name]['value'] is None:
                    super().error(ErrorType.FAULT_ERROR, f"top level is None")
            
            # verify that struct name is in scope
            in_scope = False
            dictionary_scope = None
            struct_instance = None
            
            for dict_scope in reversed(self.current_scope()):
                if struct_name in dict_scope:
                    # we save the dictionary where this struct name is located
                    dictionary_scope = dict_scope
                    in_scope = True
                    struct_instance = dict_scope[struct_name]
                    # as soon as we find the first dict that has this variable we break
                    break
            
            # variable name not in scope
            if in_scope == False:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {variable_name} has not been defined",
                )
                
            # If, during execution, the variable to the left of a dot is nil, then you must generate an error of ErrorType.FAULT_ERROR.
            if struct_instance['value'] == None:
                super().error(ErrorType.FAULT_ERROR,f"variable to the left of dot is nil",
                    )
                    
            # If, during execution, the variable to the left of a dot is not a struct type, then you must generate an error of ErrorType.TYPE_ERROR.
            if struct_instance['type'] not in self.struct_tracker:
                super().error(ErrorType.TYPE_ERROR, "struct to left of dot is not a struct type",
                    )
                
    
            struct_instance_type = struct_instance['type']
            # traverse through b.f.i ["b", "f", "i"]
            # start fom first field
            for i in range(1, len(split_var_name)):
                # get the field of the top level structure
                struct_field = split_var_name[i]  
                # If, during execution, a field name is invalid (e.g., it's not a valid field in a struct definition), then you must generate an error of ErrorType.NAME_ERROR. 
                struct_def = self.struct_tracker[struct_instance_type]
            
                does_field_exist = False
                for field in struct_def.dict['fields']:
                    if field.dict['name'] == struct_field: 
                        field_type_expected = field.dict['var_type']
                        does_field_exist = True
                        break
                # field does not exist
                if does_field_exist == False:
                    super().error(ErrorType.NAME_ERROR, f"Field to right of dot does not exist")
                    
    
                # we finished checking the last field
                if (i == len(split_var_name) - 1):
                    struct_instance = struct_instance[split_var_name[-2]]['value']
                    break
                
                if (i != 1):
                    struct_instance = struct_instance[split_var_name[i-1]]['value']
                    struct_instance_type = struct_instance[struct_field]['type']
                    continue
                
                # go deeper into nested structure
                struct_instance = struct_instance['value']
    
                # nested unallocated struct
                if (struct_instance[struct_field]['value']) is None:
                    super().error(ErrorType.FAULT_ERROR,f"nested unallocated struct")
                
                struct_instance_type = struct_instance[struct_field]['type']
                    
            
            # get expression node (the value being assigned to variable)
            expression = statement_node.dict['expression']
            # call do_evaulate_expression which handles the expression (ex: x = 5 + 6;)
            resulting_value = self.do_evaluate_expression(expression)
            # check if field type and value are compatible
            if self.is_type_compatible(field_type_expected, resulting_value) == False:
            #If the types of the target variable and source value are incompatible, you must generate an error
                super().error(ErrorType.TYPE_ERROR, f"field type and value are incompatible")
                
            
            if type(resulting_value) == int or type(resulting_value) == str or type(resulting_value) == bool:
                # adding "value" makes sure we only modfiy the value field
                    struct_instance[struct_field]['value'] = resulting_value
                    return
            
            # assign field to value
            struct_instance[struct_field]['value'] = resulting_value
            
        ############### regular variable assignment ###################### 
        # aka regular variable name with no dot operator
        else:
            # verify that variable name is in scope
            in_scope = False
            dictionary_scope = None
            for dict in reversed(self.current_scope()):
                if variable_name in dict:
                    # we save the dictionary where this vvariable name is located
                    dictionary_scope = dict
                    in_scope = True
                    # as soon as we find the first dict that has this variable we break
                    break
            
            # variable name not in scope
            if in_scope == False:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {variable_name} has not been defined",
                )
            
            # get expression node (the value being assigned to variable)
            expression = statement_node.dict['expression']
    
            # case where we try to initalize a struct to struct of diff ty[e]
            if expression.elem_type == 'new':
                new_type = expression.dict['var_type']
                if variable_name in self.current_scope()[0]:
                    variable_type = self.current_scope()[0][variable_name]['type']
                    #print(variable_type)
                    if variable_type in self.struct_tracker:
                        if (new_type != variable_type):
                            super().error( ErrorType.TYPE_ERROR, f"cant assign var to diff struct")
    
            
            # call do_evaulate_expression which handles the expression (ex: x = 5 + 6;)
            resulting_value = self.do_evaluate_expression(expression)
            
            
            # check that the resulting value matches the variables declared type
            declared_variable_type = dictionary_scope[variable_name]['type']
            
            if self.is_type_compatible(declared_variable_type, resulting_value) == False:
            #If the types of the target variable and source value are incompatible, you must generate an error
                super().error(ErrorType.TYPE_ERROR, f"type of variable and value are incompatible")
                
            # check if we are assigning an integer value/variable to a boolean variable
            if declared_variable_type == 'bool' and type(resulting_value) == int:
                resulting_value = self.int_to_bool_coercion(resulting_value)
            
            # set the value to its corresponding variable in dict   
            dictionary_scope[variable_name]['value'] = resulting_value
            
          
    # coercions from integer values/variables to boolean values/variables.
    def int_to_bool_coercion (self, value):
        if value == 0:
            return False
        else:
            return True
        
    # Citation: The following code was found on perplexiy.ai
    # Check if a value's type is compatible with the declared type     
    def is_type_compatible(self, declared_type, value):
        # only structs can be assigned to Nil (None)
        if value == None:
            if declared_type != 'int' and declared_type != 'bool' and declared_type != 'string':
                # we can only assign structs to nil
                if declared_type in self.struct_tracker:
                    return True
            return False
        if declared_type == 'int' and type(value) == int:
            return True
        elif declared_type == 'bool' and type(value) == bool:
            return True
        elif declared_type == 'string' and type(value) == str:
            return True
        # we use a dict to represent structs (check that struct exists)
        elif declared_type in self.struct_tracker and type(value) == dict:
            return True
        # Brewin++ allows coercion from int to bool (coercion)
        elif declared_type == 'bool' and type(value) == int:  
            return True  
        else:
            return False
    # end of citation 
            
    # determine which function is in the func node (print() found in statement nodes and inputi() found in expression nodes or just a general functiuon)
    def do_func_call(self, func_node):
        # only found in expression nodes
        # evaluate_input_call will help us get the user input
        if func_node.dict['name'] == 'inputi':    
            user_input = self.do_evaluate_input_call(func_node)
            return user_input
        # same as inputi but for strings
        elif func_node.dict['name'] == 'inputs':
            user_input = self.do_evaluate_input_call(func_node)
            return user_input
        elif func_node.dict['name'] == 'print':
            self.do_evaluate_print_call(func_node)
            # make sure print returns void
            return None
        else:
            # verify the func definition exists
            function = self.get_func_by_name_and_param_len(func_node.dict['name'], len(func_node.dict['args']))
            
            # remember args you pass in to functions can be expressions (ex: foo(n-1); this is handled by run_func)
            # pass in the function defintion and then pass in the arg values
            return self.run_func(function, func_node.dict['args'])
            
            
    # evaluate the print call (actually output what print wants to print)
    def do_evaluate_print_call(self, print_node):
        string_to_output = ""
        # loop through arguments of print statement
        for argument in print_node.dict['args']:
            # check if the argument is a bool so we can make it lowercase
            expression_value = self.do_evaluate_expression(argument)
            if (isinstance(expression_value, bool)):
                lowercase_bool = str(expression_value)
                string_to_output += lowercase_bool.lower()
                continue
            # we print "nil"
            if (expression_value == None):
                string_to_output += "nil"
                continue
            else:
                string_to_output += str(expression_value)
        # output using the output() method in our InterpreterBase base class (output() method automatically appends a newline character after each line it prints, so you do not need to output a newline yourself.)
        #print("STRING TO OUTPOUT", string_to_output)
        super().output(string_to_output)
        return None
        
    # get the user input 
    def do_evaluate_input_call(self, input_node):
        # If an inputi() expression has more than one parameter passed to it, then you must generate an error of type ErrorType.NAME_ERROR by calling InterpreterBase.error()
        if len(input_node.dict['args']) > 1:
            super().error(
                ErrorType.NAME_ERROR,
                f"No inputi() function found that takes > 1 parameter",
                )
            
        # If an inputi() function call has a prompt parameter, you must first output it to the screen using our InterpreterBase output() method before obtaining input from the user
        # assume that the inputi() function is invoked with a single argument, the argument will always have the type of string
        if len(input_node.dict['args']) == 1:
            input_prompt = self.do_evaluate_expression(input_node.dict['args'][0])
            super().output(input_prompt)
 
        # the user wants to input a string
        if input_node.dict['name'] == 'inputs':
            user_string_input = super().get_input()
            return user_string_input
            
        # the user wants to input an integer
        user_input = int(super().get_input())
        return user_input
    
    # Citation: The following code was found on perplexiy.ai
    def do_new_struct_instance(self, structure_type):
        # get the struct definition node
        struct_def = self.struct_tracker[structure_type]
        # Create a new instance of the struct with default field values
        # every key is the field name mapped with its valuu
        struct_instance = {}
        # create new struct instance (set its fields to default values)
        for field in struct_def.dict['fields']:
            field_name = field.dict['name']
            field_type = field.dict['var_type']
            
            if field_type == 'int':
                # struct_instance[field_name] = 0
                struct_instance[field_name] = {
                    'value' : 0,
                    'type' : field_type
                }
            elif field_type == 'bool':
                # struct_instance[field_name] = False
                struct_instance[field_name] = {
                    'value' : False,
                    'type' : field_type
                }
            elif field_type == 'string':
                # struct_instance[field_name] = ""
                struct_instance[field_name] = {
                    'value' : "",
                    'type' : field_type
                }
            # we have another struct as a field
            else:
                # check if the field type is valid
                if field_type not in self.struct_tracker:
                    super().error(ErrorType.TYPE_ERROR, f"nested field type {field_type} is unknown")   
                # else we know know the field type exists we instantiate its fields
                struct_instance[field_name] = {
                     'value' : None,
                     'type' : field_type
                }
        
        return struct_instance
    # end of citation
            
    
    # handle expression node
    def do_evaluate_expression(self, expression):
        # case where we assign a variable to an int (ex: x = 5)
        if expression.elem_type == 'int':
            return expression.dict['val']
        # case where we assign a variable to a string (ex: x = "foo")
        elif expression.elem_type == 'string':
            return expression.dict['val']
        # case where we assign a variable to a boolean
        elif expression.elem_type == 'bool':
            return expression.dict['val']
        # case where we assign a variable to a nil value (nil values are like nullptr in C++ or None in Python)
        elif expression.elem_type == 'nil':
            return None
        # case where we have an inputi() or inputs() in an expression (only the case for proj 1)
        elif expression.elem_type == 'fcall':
            # do func call will determine that it should be an input func or regular func
            func_name = expression.dict['name']
            
            # check if custom func is return void
            if (func_name,len(expression.dict['args'])) in self.func_name_to_ast:
                func_def = self.get_func_by_name_and_param_len(func_name, len(expression.dict['args']))
                # Invoking a void return type function as part of an expression should always throw an error of ErrorType.TYPE_ERROR.
                if func_def.dict['return_type'] == 'void':
                    super().error(ErrorType.TYPE_ERROR, f"can't use a func with a void return type in an expression")
  
            return self.do_func_call(expression)
        
        # case where expression node is a new command
        elif expression.elem_type == 'new':
            if expression.dict['var_type'] not in self.struct_tracker:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "struct type was not found",
                )
            struct_type = expression.dict['var_type']
            return self.do_new_struct_instance(struct_type)
                
        # case where we have a variable (x = y)
        elif expression.elem_type == 'var':
            # If an expression refers to a variable that has not yet been defined, then you must generate an error of type ErrorType.NAME_ERROR by calling InterpreterBase.error()
            var_name = expression.dict['name']
            # simple case for when we have one key and one field
            # check if var name has a dot () (if we try to do print(s1.a))
            if "." in var_name:
                split_var_name = var_name.split(".")
                if len(split_var_name) == 2:
                    struct_name = split_var_name[0]
                    struct_field = split_var_name[1]
                    #print("SPLITTTT", split_var_name)
                    
                    in_scope = False
                    struct_instance = None
                    
                    for dict in reversed(self.current_scope()):
                        if struct_name in dict:
                            in_scope = True
                            
                            # get the field and its value
                            variable_dictionary = dict.get(struct_name)
                            
                            if variable_dictionary['type'] == 'int' or variable_dictionary['type'] == 'string' or variable_dictionary['type'] == 'bool':
                                super().error(ErrorType.TYPE_ERROR, "struct to left of dot is not a struct type")
                    
                            struct_def = self.struct_tracker[variable_dictionary['type']]            
                            
                            does_field_exist = False
                            for field in struct_def.dict['fields']:
                                if field.dict['name'] == struct_field:
                                    does_field_exist = True
                                    break
                            # field does not exist
                            if does_field_exist == False:
                                super().error(ErrorType.NAME_ERROR, f"Field to right of dot does not exist")
                            

                            
                            # struct is set to nil
                            if variable_dictionary['value'] == None:
                                super().error(ErrorType.FAULT_ERROR,f"can't print field of a nil struct")
                            
                            # case where value is found
                            if type(variable_dictionary['value'][struct_field]) == int or type(variable_dictionary['value'][struct_field]) == str or type(variable_dictionary['value'][struct_field]) == bool:
                                return variable_dictionary['value'][struct_field]
                            
                            # case where element to right of field is Nil
                            if variable_dictionary['value'][struct_field]['value'] == None:
                                return None
                            
                            
                            return variable_dictionary['value'][struct_field]['value']
                    
                    # We have looped through all dicts in array and var was not found       
                    # case where var_name to left of dot was not found
                    if (in_scope == False):
                        super().error(
                            ErrorType.NAME_ERROR,
                            f"Variable {expression.dict['name']} has not been defined",
                        )

            
            # case for multiple keys
            # check if var name has a dot (if we try to do print(s1.a))
            if "." in var_name:
                # start fom first field
                split_var_name = var_name.split(".")
                struct_name = split_var_name[0]
                # verify that struct name is in scope
                in_scope = False
                struct_instance = None
                
                for dict_scope in reversed(self.current_scope()):
                    if struct_name in dict_scope:
                        # we save the dictionary where this struct name is located
                        in_scope = True
                        struct_instance = dict_scope[struct_name]
                        #print("struct_instance", struct_instance)
                        # as soon as we find the first dict that has this variable we break
                        break
                
                # variable name not in scope
                if in_scope == False:
                    super().error(
                        ErrorType.NAME_ERROR,
                        f"Variable {var_name} has not been defined",
                    )
                
                # If, during execution, the variable to the left of a dot is nil, then you must generate an error of ErrorType.FAULT_ERROR.
                if struct_instance['value'] == None:
                        super().error(ErrorType.FAULT_ERROR,f"variable to the left of dot is nil",
                        )
                        
                # If, during execution, the variable to the left of a dot is not a struct type, then you must generate an error of ErrorType.TYPE_ERROR.
                if struct_instance['type'] not in self.struct_tracker:
                        super().error(ErrorType.TYPE_ERROR, "struct to left of dot is not a struct type",
                        )
                        
                struct_instance_type = struct_instance['type']
                # traverse through b.f.i ["b", "f", "i"]
                # start fom first field
                for i in range(1, len(split_var_name)):
                    # get the field of the top level structure
                    struct_field = split_var_name[i] 
                    
                    if struct_instance_type not in self.struct_tracker:
                        super().error(ErrorType.TYPE_ERROR, "struct to left of dot is not a struct type",
                        )
                    
                    struct_def = self.struct_tracker[struct_instance_type]
                    
                    does_field_exist = False
                    for field in struct_def.dict['fields']:
                        if field.dict['name'] == struct_field:
                            #field_type_expected = field.dict['var_type']
                            does_field_exist = True
                            break
                    # field does not exist
                    if does_field_exist == False:
                        super().error(ErrorType.NAME_ERROR, f"Field to right of dot does not exist")
                        
                    # we finished checking the last field
                    if (i == len(split_var_name) - 1):
                        struct_instance = struct_instance[split_var_name[-2]]['value']
                        break   

                    # go deeper into nested structure
                    #print("STRUCT INSTANCE AFTER YAY", struct_instance['value'])
                    if (i != 1):
                        #struct_instance = struct_instance[struct_field['value']
                        struct_instance = struct_instance[split_var_name[i-1]]['value']
                        struct_instance_type = struct_instance[struct_field]['type']
                        continue

                    # go deeper into nested structure
                    struct_instance = struct_instance['value']
                    # check if filed value is nil
                    if (struct_instance[struct_field]['value']) is None:
                        super().error(ErrorType.FAULT_ERROR, f'field is none')
                    
                    struct_instance_type = struct_instance[struct_field]['type']
                
                # return the value at that field
                return struct_instance[struct_field]['value']
            
            else:   
                # check if the variable was defined at all     
                for dict in reversed(self.current_scope()):
                    if expression.dict['name'] in dict:
                        # return variable value
                        vaiable_name = dict.get(expression.dict['name'])
                        return vaiable_name['value']
                    
                
                # We have looped through all dicts in array and var was not found
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {expression.dict['name']} has not been defined",
                )

        elif expression.elem_type == '*':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # special case to handle booleans which python interprets as ints
            if isinstance(operand1_value, bool) or isinstance(operand2_value, bool):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
                return operand1_value * operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
                
        elif expression.elem_type == '/':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
                        
            # special case to handle booleans which python interprets as ints
            if isinstance(operand1_value, bool) or isinstance(operand2_value, bool):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
                return operand1_value // operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )     

        # case where we add 
        elif expression.elem_type == '+':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # special case to handle booleans which python interprets as ints
            if isinstance(operand1_value, bool) or isinstance(operand2_value, bool):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            # if both the operands are of type int or string (concatenate them)
            elif isinstance(operand1_value, int) and isinstance(operand2_value, int) or isinstance(operand1_value, str) and isinstance(operand2_value, str):
                return operand1_value + operand2_value       
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
        
        # case where we subtract
        elif expression.elem_type == '-':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
                        
            # special case to handle booleans which python interprets as ints
            if isinstance(operand1_value, bool) or isinstance(operand2_value, bool):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
                
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
                return operand1_value - operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
                 
                 
        elif expression.elem_type == '==':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            
            # check that only strcuts are compared to nil
            if self.do_evaluate_expression(operand2) == None:
                # handles wnere var is not defined
                operand1_value = self.do_evaluate_expression(operand1)
                # check that we only compare structs to nil
                if type(operand1_value) == int or type(operand1_value) == str or type(operand1_value) == bool:
                    super().error(ErrorType.TYPE_ERROR, f"cant compare nonstruct to nil")
                # we know its an int at this point
                if operand1.elem_type == 'var':
                    if (operand1_value == None):
                        return True
                    # struct is not None
                    else:
                        return False
                
            if self.do_evaluate_expression(operand1) == None:
                # handles wnere var is not defined
                operand2_value = self.do_evaluate_expression(operand2)
                # check that we only compare structs to nil
                if type(operand2_value) == int or type(operand2_value) == str or type(operand2_value) == bool:
                    super().error(ErrorType.TYPE_ERROR, f"cant compare nonstruct to nil")
                if operand2.elem_type == 'var':
                    if (operand2_value == None):
                        return True
                    # struct is not None
                    else:
                        return False

            # check that we are comparing strucs of same type
            if operand1.elem_type == 'var' and operand2.elem_type == 'var':
                operand1name = operand1.dict['name']
                operand2name = operand2.dict['name']
                if operand1name in self.call_stack[-1][0] and operand2name in self.call_stack[-1][0]:
                    operand1type = self.call_stack[-1][0][operand1name]['type']
                    operand2type = self.call_stack[-1][0][operand2name]['type']
                    if (operand1type in self.struct_tracker and operand2type in self.struct_tracker):
                        # handles struct comparison (true if point to same object)
                        if (operand1type != operand2type):
                            super().error(ErrorType.TYPE_ERROR, f"can't compare unrelated types {operand1type} and {operand2type}")
                        # compares structs by reference
                        if self.call_stack[-1][0][operand1name]['value'] is self.call_stack[-1][0][operand2name]['value']:
                            return True
                            
            # handle case where we compare two structs (compare by object reference)
            if operand1.elem_type == 'var' and operand2.elem_type == 'var':
                operand1_value = self.do_evaluate_expression(operand1)
                operand2_value = self.do_evaluate_expression(operand2)
                if type(operand1_value) != bool and type(operand1_value) != str and type(operand1_value) != int:
                    if type(operand2_value) != bool and type(operand2_value) != str and type(operand2_value) != int:
                        if operand1_value is operand2_value:
                            return True
                        else: 
                            return False
            
            
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # from here if we have a struct we know there is an issue
            if type(operand1_value) != str and type(operand1_value) != bool and type(operand1_value) != int:
                super().error(ErrorType.TYPE_ERROR, f"cant compare struct to primitive")   
                
            if type(operand2_value) != str and type(operand2_value) != bool and type(operand2_value) != int:
                super().error(ErrorType.TYPE_ERROR, f"cant compare struct to primitive")   
                
            
            # if both the operands are nil (None) return true
            if (operand1_value == None and operand2_value == None):
                return True
            
            # an attempt to compare a void type (e.g., the return of print()) to any other type must result in an error of ErrorType.TYPE_ERROR.
            #if 
            if (operand1_value == 'void' or operand2_value == 'void'):
                super().error(ErrorType.TYPE_ERROR, "Can't compare void type")
            
            # check for comparing ints to bools which is allowed
            # e.g., 5 == true would be true, false == 0 would be true
            # have to be careful that we dont change an int to a bool if we actually want to compare two ints
            if type(operand1_value) != type(operand2_value):
                if type(operand1_value) == int:
                    operand1_value = self.int_to_bool_coercion(operand1_value)
                if type(operand2_value) == int:
                    operand2_value = self.int_to_bool_coercion(operand2_value)
                    
            # cant compare bool to string
            if (type(operand1_value) == bool and type(operand2_value) == str) or (type(operand2_value) == bool and type(operand1_value) == str):
                super().error(ErrorType.TYPE_ERROR, "Can't compare values of diff types")
            
            # if both the operands are of type int or type string or type bool
            if isinstance(operand1_value, int) and isinstance(operand2_value, int) or isinstance(operand1_value, str) and isinstance(operand2_value, str) or isinstance(operand1_value, bool) and isinstance(operand2_value, bool):
                return operand1_value == operand2_value
            else:
                # values of diff types safety check
                # super().error(ErrorType.TYPE_ERROR, "Can't compare values of diff types")
                return False
        
        elif expression.elem_type == '!=':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
    
            # check that only strcuts are compared to nil
            if self.do_evaluate_expression(operand2) == None:
                # handles wnere var is not defined
                operand1_value = self.do_evaluate_expression(operand1)
                # check that we only compare structs to nil
                if type(operand1_value) == int or type(operand1_value) == str or type(operand1_value) == bool:
                    super().error(ErrorType.TYPE_ERROR, f"cant compare nonstruct to nil")
                if operand1.elem_type == 'var':
                    if (operand1_value == None):
                        return False
                    # struct is not None
                    else:
                        return True
                        
            if self.do_evaluate_expression(operand1) == None:
                # handles wnere var is not defined
                operand2_value = self.do_evaluate_expression(operand2)
                # check that we only compare structs to nil
                if type(operand2_value) == int or type(operand2_value) == str or type(operand2_value) == bool:
                    super().error(ErrorType.TYPE_ERROR, f"cant compare nonstruct to nil")
                if operand2.elem_type == 'var':
                    if (operand2_value == None):
                        return False
                    # struct is not None
                    else:
                        return True
            
            if operand1.elem_type == 'var' and operand2.elem_type == 'var':
                operand1_value = self.do_evaluate_expression(operand1)
                operand2_value = self.do_evaluate_expression(operand2)
                
                if type(operand1_value) != bool and type(operand1_value) != str and type(operand1_value) != int:
                    if type(operand2_value) != bool and type(operand2_value) != str and type(operand2_value) != int:
                        if operand1_value is operand2_value:
                            return False
                        else: 
                            return True
            
            # check that are are comparing strucs of same type
            if operand1.elem_type == 'var' and operand2.elem_type == 'var':
                operand1name = operand1.dict['name']
                operand2name = operand2.dict['name']
                if operand1name in self.call_stack[-1][0] and operand2name in self.call_stack[-1][0]:
                    operand1type = self.call_stack[-1][0][operand1name]['type']
                    operand2type = self.call_stack[-1][0][operand2name]['type']
                    if (operand1type in self.struct_tracker and operand2type in self.struct_tracker):
                        # compares structs by reference
                        if self.call_stack[-1][0][operand1name]['value'] is self.call_stack[-1][0][operand2name]['value']:
                            return False
                        if (operand1type != operand2type):
                            super().error(ErrorType.TYPE_ERROR, f"can't compare unrelated types {operand1type} and {operand2type}")
            
            
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # from here if we have a struct we know there is an issue
            if type(operand1_value) != str and type(operand1_value) != bool and type(operand1_value) != int:
                super().error(ErrorType.TYPE_ERROR, f"cant compare struct to primitive")   
                
            if type(operand2_value) != str and type(operand2_value) != bool and type(operand2_value) != int:
                super().error(ErrorType.TYPE_ERROR, f"cant compare struct to primitive")   
            
            # if both the operands are nil (None)
            if (operand1_value == None and operand2_value == None):
                return False
            
            # an attempt to compare a void type (e.g., the return of print()) to any other type must result in an error of ErrorType.TYPE_ERROR.
            if (operand1_value == 'void' or operand2_value == 'void'):
                super().error(ErrorType.TYPE_ERROR, "Can't compare void type")
            
            # check for comparing ints to bools which is allowed
            # e.g., 5 == true would be true, false == 0 would be true
            # have to be careful that we dont change an int to a bool if we actually want to compare two ints
            if type(operand1_value) != type(operand2_value):
                if type(operand1_value) == int:
                    operand1_value = self.int_to_bool_coercion(operand1_value)
                if type(operand2_value) == int:
                    operand2_value = self.int_to_bool_coercion(operand2_value)
                    
            # cant compare bool to string
            if (type(operand1_value) == bool and type(operand2_value) == str) or (type(operand2_value) == bool and type(operand1_value) == str):
                super().error(ErrorType.TYPE_ERROR, "Can't compare values of diff types")
        
            # if both the operands are of type int or type string or type bool
            if isinstance(operand1_value, int) and isinstance(operand2_value, int) or isinstance(operand1_value, str) and isinstance(operand2_value, str) or isinstance(operand1_value, bool) and isinstance(operand2_value, bool):
                # compare operands
                return operand1_value != operand2_value
            else:
                # # values of diff types safety check
                # we return true since != says they are not equal
                return True
            
                
        elif expression.elem_type == '<':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # an attempt to compare a void type (e.g., the return of print()) to any other type must result in an error of ErrorType.TYPE_ERROR.
            if (operand1_value == 'void' or operand2_value == 'void'):
                super().error(ErrorType.TYPE_ERROR, "Can't compare void type")
            
            # special case to handle booleans which python interprets as ints
            if isinstance(operand1_value, bool) or isinstance(operand2_value, bool):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
                # compare operands
                return operand1_value < operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
                
        elif expression.elem_type == '<=':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # an attempt to compare a void type (e.g., the return of print()) to any other type must result in an error of ErrorType.TYPE_ERROR.
            if (operand1_value == 'void' or operand2_value == 'void'):
                super().error(ErrorType.TYPE_ERROR, "Can't compare void type")
                        
            # special case to handle booleans which python interprets as ints
            if isinstance(operand1_value, bool) or isinstance(operand2_value, bool):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
                # compare operands
                return operand1_value <= operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
                
        elif expression.elem_type == '>':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # an attempt to compare a void type (e.g., the return of print()) to any other type must result in an error of ErrorType.TYPE_ERROR.
            if (operand1_value == 'void' or operand2_value == 'void'):
                super().error(ErrorType.TYPE_ERROR, "Can't compare void type")
                 
            # special case to handle booleans which python interprets as ints
            if isinstance(operand1_value, bool) or isinstance(operand2_value, bool):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
                # compare operands
                return operand1_value > operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
                
        elif expression.elem_type == '>=':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # an attempt to compare a void type (e.g., the return of print()) to any other type must result in an error of ErrorType.TYPE_ERROR.
            if (operand1_value == 'void' or operand2_value == 'void'):
                super().error(ErrorType.TYPE_ERROR, "Can't compare void type")
                        
            # special case to handle booleans which python interprets as ints
            if isinstance(operand1_value, bool) or isinstance(operand2_value, bool):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
                # compare operands
                return operand1_value >= operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )                
        
        # unary operation: negation - (ex: -5)
        elif expression.elem_type == 'neg':
            # get the operand
            operand1 = expression.dict['op1']
            # get the operand value
            operand1_value = self.do_evaluate_expression(operand1)
            
            # operand must be of type int (handles case hwere bool is not intepreted as int)
            if isinstance(operand1_value, int) and type(operand1_value) != bool:
                # negate the value
                return -operand1_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )         
            
        # unary operation: logical not ! (ex: !true)
        elif expression.elem_type == '!':
            # get the operand
            operand1 = expression.dict['op1']
            
            # get the operand value
            operand1_value = self.do_evaluate_expression(operand1)
            if type(operand1_value) == int:
                operand1_value = self.int_to_bool_coercion(operand1_value)
            
            # operand must be of type bool
            if isinstance(operand1_value, bool):
                # logical negation (Python uses the keyword not)
                return not operand1_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )       
                
        # and operator
        elif expression.elem_type == '&&':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # checking the value of an integer in an and/or expression, e.g., if (int_variable || bool_variable && other_int_variable) { /* do this */ }
            if type(operand1_value) == int:
                operand1_value = self.int_to_bool_coercion(operand1_value)
            if type(operand2_value) == int:
                operand2_value = self.int_to_bool_coercion(operand2_value)  
            
            
            # if both the operands are of type bool
            if isinstance(operand1_value, bool) and isinstance(operand2_value, bool):
                # compare operands
                return operand1_value and operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )   
            
        # or operator
        elif expression.elem_type == '||':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
            # checking the value of an integer in an and/or expression, e.g., if (int_variable || bool_variable && other_int_variable) { /* do this */ }
            if type(operand1_value) == int:
                operand1_value = self.int_to_bool_coercion(operand1_value)
            if type(operand2_value) == int:
                operand2_value = self.int_to_bool_coercion(operand2_value)  
            
            # if both the operands are of type bool
            if isinstance(operand1_value, bool) and isinstance(operand2_value, bool):
                # compare operands
                return operand1_value or operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )     
    

    def current_scope(self):
        # Return the current scope (top of the stack) (the scope is an a list of dictonaries, every dictionary corresponds to the functions scope and if/for loop scopes in that function)
        return self.call_stack[-1] 
    
    

    
####################### proj 3 test cases ##########################
    
#     test_ret1 = """
#         func main() : int {
#             print(foo());
#         }
#         func foo() : int {
#             return 1;
#         }  
#         """
        
#     test_print = """
#                 func main() : void {
#                     print(5);
#                     print("Hello, Brewin++!");
#                     print("Hello");
#                     print("World");
#                 }
#                 """
                
#     test_int_return_from_func = """
#                         func main() : void {
#                             print(getFive());
#                         }

#                         func getFive() : int {
#                             return 5;
#                         }
#                         """


#     test_basic_addition = """
#                 func main() : void {
#                     print(add(2, 3));
#                 }

#                 func add(a: int, b: int) : int {
#                     return a + b;
#                 }
#                 """
                
#     test_define_and_print = """
#             func main() : void {
#                 var x: int;
#                 x = 10;
#                 print(x);
#             }
#             """
            
#     # should throw a type error
#     test_assign1 = """
#                 func main() : int {
#                     var a: int; 
#                     a = true;
#                     print(a);
#                 }
#                 """
                
#     #should throw a type error
#     test_pass2 = """
#             func main() : void {
#                 var a: bool; 
#                 a = true;
#                 foo(a);
#             }
            
#             func foo(x:int) : void {
#                 print(x);
#             }
#             """
        
#     # should throw a fault error
#     test_assign_nil = """
#             struct s {
#                 a:int;
#             }

#             func main() : int {
#                 var x: s;
#                 x = new s;
#                 x = nil;
#                 print(x.a);
                
#             }
#             """
            
            
#     test_struct2 = """
#     struct foo {
#         i:int;
#     }

#     struct bar {
#         f:foo;
#     }

#     func main() : void {
#         var b : bar;
#         b = new bar;
#         b.f.i = 10;
#         print(b.f.i);
#     }
#     """
    
    
#     test_multi_dot = """
#         struct ant {
#             i:int;
#         }

#         struct bat {
#             a:ant;
#         }

#         struct cat {
#             b:bat;
#         }

#         struct dog {
#             c:cat;
#         }

#         func main() : int {
#             var d: dog; 
#             d = new dog;
#             d.c = new cat;
#         }
#         """
    
#     test_struct2 = """

#         struct foo {
#             i:int;
#         }

#         struct bar {
#             f:foo;
#         }

#         func main() : void {
#             var b : bar;
#             b = new bar;
#             b.f = new foo;
#             b.f.i = 10;
#             print(b.f.i);
#         }
#         """

#     test_struct1 = """
#         struct foo {
#             a:int;
#             b:bool;
#             c:string;
#         }

#         func main() : void {
#             var s1 : foo;
#             print(s1);

#             s1 = new foo;
#             print(s1.a);
#             print(s1.b);
#             print(s1.c);
            
#             s1.a = 10;
#             s1.b = true;
#             s1.c = "barf";
#             print(s1.a);
#             print(s1.b);
#             print(s1.c);
#         }
#     """

#     test_multi_dot = """
    
#         struct ant {
#             i:int;
#         }
        
#         struct bat {
#             a:ant;
#         }

#         struct cat {
#             b:bat;
#         }

#         struct dog {
#             c:cat;
#         }

#         func main() : int {
#         var d: dog; 
#         d = new dog;
#         d.c = new cat;
#         d.c.b = new bat;
#         d.c.b.a = new ant;
#         d.c.b.a.i = 15;
        
#         print(d.c.b.a.i);
#         }
#     """

#     test_challenge1 = """
    
#     struct list {
#     val: int;
#     next: list;
# }

# func cons(val: int, l: list) : list {
#     var h: list;
#     h = new list;
#     h.val = val;
#     h.next = l;
#     return h;
# }

# func rev_app(l: list, a: list) : list {
#     if (l == nil) {
#         return a;
#     }

#     return rev_app(l.next, cons(l.val, a));
# }

# func reverse(l: list) : list {
#     var a: list;

#     return rev_app(l, a);
# }

# func print_list(l: list): void {
#     var x: list;
#     var n: int;
#     for (x = l; x != nil; x = x.next) {
#         print(x.val);
#         n = n + 1;
#     }
#     print("N=", n);
# }

# func main() : void {
#     var n: int;
#     var i: int;
#     var l: list;
#     var r: list;

#     n = inputi();
#     for (i = n; i; i = i - 1) {
#         var n: int;
#         n = inputi();
#         l = cons(n, l);
#     }
#     r = reverse(l);
#     print_list(r);
# }
#             """
            
            
#     test_spec_trust = """
#         struct Person { 
#         name: string; 
#         age: int; 
#         student: bool;
#         }
        
#         func main() : void { 
#         var p: Person;
#         p = new Person; 
#         p.name = "Carey"; 
#         p.age = 21; 
#         p.student = false; 
#         foo(p);
#         }
        
#         func foo(p : Person) : void {
#         print(p.name, " is ", p.age, " years old.");
#         }               
#                 """
             
#     test_spec_nil = """
#         struct dog {
#             name: string; 
#             vaccinated: bool;
#         }
#         func main() : void {
#         var d: dog;    /* d is an object reference whose value is nil */
#         print (d == nil);  /* prints true, because d was initialized to nil */
#         }
#             """    
        
        
#     test_spec_false_nil = """
#     struct flea {
#         age: int;
#         infected : bool;
#     }
#     struct dog {
#         name: string; 
#         vaccinated: bool; 
#         companion: flea;
#     }
#     func main() : void {
#         var d: dog;
#         d = new dog; /* sets d object reference to point to a dog structure */
#         print(d.vaccinated); /* prints false - default bool value */
#         print(d.companion); /* prints nil - default struct object reference */
#         /* we may now set d's fields */
#         d.name = "Koda"; 
#         d.vaccinated = true;
#         d.companion = new flea;
#         d.companion.age = 3;
#         print("d AFTER COMPANION", d);
#         print(d.companion.age);
#     }
#     """

#     test_oscar = """
    
#         struct Person {
#       name: string;
#       age: int;
#       student: bool;
#       friend: Person;
#     }
    
    
#     struct Dog {
#         name: string;
#         dog_years: int;
#         sibilings: Dog;
#       }


#       func main() : void {
#         var a: Person;
#         a = new Person;
#         a.name = "bruh";
#         a.friend = new Person;
#         a.friend.name = "friend 2";
#         a.friend.friend = new Person;
#         a.friend.friend.name = "friend 3";
#         print(a.name);
#         print(a.friend.friend.name);
#       }
    
    
#     """
    
#     test_pass_by_or1 = """
#         struct foo {
#             a:int;
#             }

#         func main() : int {
#             var f: foo; 
#             f = new foo;
#             var ten: int;
#             ten = 10;
#             f.a = ten;
#             foo(f);
#             print(f.a);
#             print(ten);
#         }

#         func foo(x:foo) : void {
#             x.a = 20;
#         }
#     """
    
#     # should be a fault error
#     test_assign_nil = """
#     struct s {
#         a:int;
#     }

#     func main() : int {
#         var x: s;
#         x = new s;
#         x = nil;
#         print(x.a);
#     }
#     """

#     #should be a TYPE Error
#     test_cmp_void3 = """
    
#     func main() : void {
#         var b: bool;
#         b = foo() == nil;
#         print(foo());
#     }

#     func foo() : void {
#         var a: int;
#     }  
#     """







# ########## student Test cases ############################


# def main():
    
# #     test_brewinpp = """
    
# #         func main() : void {
# #         var n : int;
# #         n = inputi("Enter a number: ");
# #         print(fact(n));
# #         }

# #         func fact(n : int) : int {
# #         if (n <= 1) { return 1; }
# #         return n * fact(n-1);
# # }
    
# #     """
    
# #     test_coerce_struct = """
# #     struct animal {
# #     name : string;
# #     noise : string;
# #     color : string;
# #     extinct : bool;
# #     ears: int; 
# #     }
# #     func main() : void {
# #     var pig : animal;
# #     var extinct : bool;
# #     extinct = make_pig(pig, 0);
# #     print(extinct);
# #     }
# #     func make_pig(a : animal, extinct : int) : bool{
# #     if (a == nil){
# #         print("making a pig");
# #         a = new animal;
# #     }
# #     a.extinct = extinct;
# #     return a.extinct;
# # }
# #     """
    
# #     test_coercion1 = """
# #     func main() : void {
# #   print(5 || false);
# #   var a:int;
# #   a = 1;
# #   if (a) {
# #     print("if works on integers now!");
# #   }
# #   foo(a-1);
# # }

# # func foo(b : bool) : void {
# #   print(b);
# # }
# # """

# #     test_default_ret1 = """
# #     func main() : void {
# #         print(foo());
# #         print(bar());
# #     }

# #     func foo() : int {
# #         return; /* returns 0 */
# #     }
    
# #     func bar() : bool { 
# #         print("bar");
# #     }  /* returns false*/
    
# #     """
    
# #     test_default_ret2 = """
# #     struct dog {
# #         bark: int;
# #         bite: int;
# #     }

# #     func bar() : int {
# #         return;  /* no return value specified - returns 0 */
# #     }

# #     func bletch() : bool {
# #         print("hi");
# #         /* no explicit return; bletch must return default bool of false */
# #     }

# #     func boing() : dog {
# #         return;  /* returns nil */
# #     }

# #     func main() : void {
# #         var val: int;
# #         val = bar();
# #         print(val);  /* prints 0 */
# #         print(bletch()); /* prints false */
# #         print(boing()); /* prints nil */
# #     }
# #     """
    
# #     test_functions1 = """
# #     func foo(a:int, b:string, c:int, d:bool) : int {
# #         print(b, d);
# #         return a + c;
# #     }

# #     func talk_to(name:string): void {
# #         if (name == "Carey") {
# #             print("Go away!");
# #             return;  /* using return is OK w/void, just don't specify a value */
# #         }
# #         print("Greetings");
# #     }

# #     func main() : void {
# #         print(foo(10, "blah", 20, false));
# #         talk_to("Bonnie");
# #     }
# #     """
    
# #     test_nil_ret = """
# #     struct person {
# #         name : string;
# #     }
# #     func incorrect() : int{
# #         var x : int;
# #         return 9;
# #     }
# #     func correct() : person{
# #         print("i should print");
# #         return nil;
# #     }
# #     func main() : void{
# #         print("hi");
# #         correct();
# #         incorrect();
# #     }  
# #     """
    
    
# #     test_nil_ret2 = """
# #     struct person {
# #     name : string;
# #     }
# #     func incorrect() : int{
# #     var x : int;
# #     return 9;
# #     }
# #     func correct() : person{
# #     print("i should print");
# #     return;
# #     }
# #     func main() : void{
# #     var p : person;
# #     print("hi");
# #     p = correct();
# #     print(p);
# #     print(correct());
# #     incorrect();
# #     }
# #     """
    
# #     test_nil_struct = """
# #         struct animal {
# #         name : string;
# #         noise : string;
# #         color : string;
# #         extinct : bool;
# #         ears: int; 
# #     }
# #     func main() : void {
# #     var pig : animal;
# #     var noise : string;
# #     noise = make_pig(pig);
# #     print(noise);
# #     }
# #     func make_pig(a : animal) : string{
# #     if (a == nil){
# #         print("making a pig");
# #         a = new animal;
# #     }
# #     a.noise = "oink";
# #     return a.noise;
# #     }
# #     """
    
# #     test_obj_ref1 = """
# #     struct dog {
# #     name: string;
# #     vaccinated: bool;  
# #     }

# #     func main() : void {
# #     var d: dog;
# #     d = new dog;
# #     steal_dog(d, "My new Dog");
# #     print(d.name);
# #     }

# #     func steal_dog(d : dog, name: string) : void {
# #     d.name = name;
# #     }
# #     """
    
# #     test_obj_ref2 = """
# #     struct dog {
# #   name: string;
# #   vaccinated: bool;  
# # }

# # func main() : void {
# #   var d: dog;
# #   d = steal_dog(new dog, "Spots");
# #   print(d.name);

# #   }

# # func steal_dog(d : dog, name: string) : dog {
# #   d.name = name;
# #   return d;
# # }
# #     """
    
# #     test_obj_ref3 = """
# #     struct dog {
# #  bark: int;
# #  bite: int;
# # }

# # func foo(d: dog) : dog {  /* d holds the same object reference that the koda variable holds */
# #   d.bark = 10;
# #   return d;  		/* this returns the same object reference that the koda variable holds */
# # }

# #  func main() : void {
# #   var koda: dog;
# #   var kippy: dog;
# #   koda = new dog;
# #   kippy = foo(koda);	/* kippy holds the same object reference as koda */
# #   kippy.bite = 20;
# #   print(koda.bark, " ", koda.bite); /* prints 10 20 */
# # }
# #     """
    
# #     test_self_ref_struct = """
# #     struct node {
# #         value: int;
# #         next: node;
# #     }

# #     func main() : void {
# #         var n : node;
# #           print(n);
# #           n = new node;
# #           print(n.value);
# #           print(n.next);
          
# #     }
# #     """
    
# #     test_self_ref_struct2 = """
# #     struct node {
# #   value: int;
# #   next: node;
# # }

# # func main() : void {
# #   var n : node;
# #   var p : node;
# #   var q : node; 
# #   print(n);
# #   n = new node;
# #   p = new node;
# #   q = new node;
# #   n.value = 9;
# #   n.next = p;
# #   print(n.value);
# #   p.value = 9;
# #   print(p.value);
# #   print(p.next);
# #   print(n.next.value);
# #   n.next.next = q;
# #   n.next.next.value = 10;
# #   print(p.next.value);
# #   print(q.value + 1);
# # }
# #     """
    
# #     test_structs_1 = """
# #     struct flea {
# #   age: int;
# #   infected : bool;
# # }

# # struct dog {
# #   name: string;
# #   vaccinated: bool;  
# #   companion: flea;
# # }

# # func main() : void {
# #   var d: dog;     
# #   d = new dog;   /* sets d object reference to point to a dog structure */

# #   print(d.vaccinated); /* prints false - default bool value */
# #   print(d.companion); /* prints nil - default struct object reference */

# #   /* we may now set d's fields */
# #   d.name = "Koda";
# #   d.vaccinated = true;
# #   d.companion = new flea;
# #   d.companion.age = 3; 
# # }
    
# #     """
    
# #     test_structs1 = """
# # struct Person {
# #   name: string;
# #   age: int;
# #   student: bool;
# # }

# # func main() : void {
# #   var p: Person;
# #   p = new Person;
# #   p.name = "Carey";
# #   p.age = 21;
# #   p.student = false;
# #   foo(p);
# # }

# # func foo(p : Person) : void {
# #   print(p.name, " is ", p.age, " years old.");
# # } 
    
    
# #     """
    
# #     test_structs2 = """
# #     struct animal {
# #     name : string;
# #     extinct : bool;
# #     ears: int; 
# # }
# # func main() : void {
# #    var pig : animal;
# #    var ret: bool;
# #    ret = is_extinct(pig);
# #    print(ret);
# #    pig = new animal;
# #    pig.extinct = true;
# #    ret = is_extinct(pig);
# #    print(ret);
# #    destroy_animals("pig", pig);
# #    print(pig.extinct);
   
# # }
# # func is_extinct(p : animal) : bool {
# #   if (p == nil){
# #     print("i go in here first");
# #     return 0;
# #   }
# #   else{
# #     return p.extinct;
# #   }
# # }
# # func destroy_animals(name: string, p : animal) : animal{
# #   if (p==nil){
# #      p = new animal;
# #   }
# #   name = inputs("What animal do you want to destroy?");
# #   p.name = name;
# #   p.extinct = true;
# #   print("Destroyed animal ", p.name);
# #   return nil;
# # }
    
# #     """
    
# #     test_structs3 = """
# #     struct animal {
# #     name : string;
# #     extinct : bool;
# #     ears: int; 
# # }
# # func main() : void {
# #    var pig : animal;
# #    var ret: bool;
# #    var hm : animal;
# #    ret = is_extinct(pig);
# #    print(ret);
# #    pig = new animal;
# #    pig.extinct = true;
# #    ret = is_extinct(pig);
# #    print(ret);
# #    hm = destroy_animals("pig", pig);
# #    print(pig.extinct);
# #    print(hm);
   
# # }
# # func is_extinct(p : animal) : bool {
# #   if (p == nil){
# #     print("i go in here first");
# #     return 0;
# #   }
# #   else{
# #     return p.extinct;
# #   }
# # }
# # func destroy_animals(name: string, p : animal) : animal{
# #   if (p==nil){
# #      p = new animal;
# #   }
# #   name = inputs("What animal do you want to destroy?");
# #   p.name = name;
# #   p.extinct = true;
# #   print("Destroyed animal ", p.name);
# #   return nil;
# # }
# #     """
    
# #     test_unitnit_struct = """
    
# #     struct dog {
# #   name: string;
# #   vaccinated: bool;  
# # }

# # func main() : void {
# #   var d: dog;    /* d is an object reference whose value is nil */

# #   print (d == nil);  /* prints true, because d was initialized to nil */
# # }
    
# #     """
    
    
# #     ####################### fails ####################
# #     test_dot_op1 = """
# #     func main() : void {
# #         var x : int;
# #         x = 5;
# #         print(x.name);
# #     }
# #     """
    
# #     test_dot_op2 = """
# #     struct animal {
# #     name : string;
# #     noise : string;
# #     color : string;
# #     extinct : bool;
# #     ears: int; 
# # }
# # func main() : void {
# #    var pig : animal;
# #    pig.noise = "oink";
# # }
# #     """
    
# #     test_dot_op3 = """
# #     struct animal {
# #     name : string;
# #     noise : string;
# #     color : string;
# #     extinct : bool;
# #     ears: int; 
# # }
# # func main() : void {
# #    var pig : animal;
# #    pig = new animal;
# #    pig.tail = true;
# # }
# #     """
    
# #     test_incorrect_return_1 = """
# #         func main() : void {
# #   print(foo());
# #   print(bar());
# # }

# # func foo() : int {
# #   return "string"; /* returns 0 */
# # }

# # func bar() : bool {
# #   print("bar");
# # }  /* returns false*/
    
# #     """
    
    
# #     test_invalid_coerce = """
    
# #     struct animal {
# #     name : string;
# #     noise : string;
# #     color : string;
# #     extinct : bool;
# #     ears: int; 
# # }
# # func main() : void {
# #    var pig : animal;
# #    var extinct : bool;
# #    extinct = make_pig(pig, false);
# #    print(extinct);
# # }
# # func make_pig(a : animal, extinct : int) : bool{
# #   if (a == nil){
# #     print("making a pig");
# #     a = new animal;
# #   }
# #   a.extinct = extinct;
# #   return a.extinct;
# # }
    
# #     """
    
# #     test_invalid_param_type = """
# #     func foo(a:invinal) : int {
# #         print("i shouldn't print");
# #     }
# #     func main() : void {
# #         print("i shouldn't print either");
# #     }
# #     """
    
# #     test_invalid_param = """
# #     struct animal {
# #         name : string;
# #         noise : string;
# #         color : string;
# #         extinct : bool;
# #         ears: int; 
# #     }
# #     struct person {
# #         name: string;
# #         height: int;
# #     }
# #     func main() : void {
# #         var pig : animal;
# #         var p : person;
# #         var noise : string;
# #         noise = make_pig(p, "oink");
# #         print(noise);
# #     }
# #     func make_pig(a : animal, noise : string) : string{
# #         if (a == nil){
# #             print("making a pig");
# #             a = new animal;
# #         }
# #         a.noise = noise;
# #         return a.noise;
# #     }
# #     """
    
# #     test_invalid_ret_type = """
# #     func foo(a: int) : invalidint {
# #         print("i shouldn't print");
# #         }
# #     func main() : void {
# #     print("i shouldn't print either");
# #     }
    
    
# #     """
    
# #     test_invalid_type1 = """
# #     func main() : void {
# #         print("i should print");
# #         var x : invalid;
# #     }
# #     """
    
#     test_nil_ret_invalid = """
#     func incorrect() : nil {
#         print(nil);
#     }
#     func main() : void{
#         print("hi");
#         incorrect();
#     }
#     """
    
#     test_nil3 = """
#     func incorrect() : int{
#         var x : int;
#     }
#     func main() : void{
#         print("hi");
#         incorrect();
#         var x : int;
#         x = nil;
#         print(x);
#     }
    
#     """
    
#     test_undefined_param_type = """
    
#     func foo(a) : int {
#   print("i shouldn't print");
# }
# func main() : void {
#  print("i shouldn't print either");
# }

    
#     """
    
#     test_undefined_ret_type = """
#         func foo(a) {
#         print("i shouldn't print");
#         }
#         func main() : void {
#         print("i shouldn't print either");
#         }
#     """
    
#     test_undefined_struct = """
#     struct dog {
#         name: string;
#         vaccinated: bool;  
#     }

#     func main() : void {
#         var d: cat;
#         print("i shouldn't print");
#     } 
#     """
    
#     test_unknown_type_1 = """
#         func main() : void {
#  print("i should print");
#  var x;
# }
    
#     """
    
#     test_random_spec = """
#     struct A {
#         x: int;
#     }
#     struct B {
#         x: int;
#     }

#     func main(): void {
#         var a: A;
#         var b: B;
#         a = getAnil();
#         b = getBnil();
#         print(a);
#         print(b);
#         print("fine so far");
#         return;
#     }

#     func getAnil() : A {
#         return nil;
#     }

#     func getBnil() : B {
#         return nil;
#     }
#     struct A {
#         x: int;
#     }
#     struct B {
#         x: int;
#     }

#     func main(): void {
#         var a: A;
#         var b: B;
#         a = getAnil();
#         b = getBnil();
#         print(a);
#         print(b);
#         print("fine so far");
#         return;
#     }

#     func getAnil() : A {
#         return nil;
#     }

#     func getBnil() : B {
#         return nil;
#     }
        
#     """
    

    
#     test_random_spec = """
    
#     struct A {
#         x: int;
#     }
#     struct B {
#         x: int;
#     }

#     func main(): void {
#         var a: A;
#         var b: B;
#         a = getAnil();
#         b = getBnil();
#         print(a);
#         print(b);
#         print("fine so far");
#         return;
#     }

#     func getAnil() : A {
#         return nil;
#     }

#     func getBnil() : B {
#         return nil;
#     }
        
#     """
    
#     test_random_spec2 = """
#         struct A {
#             x: int;
#         }
#         struct B {
#             x: int;
#         }
        
#         func main(): void {
#             getA();
#             return;
#         }

#         func getA() : A {
#             var b: B;
#             b = nil;
#             return b;
#         }
#     """
    
#     test_jenn = """
#     struct Dog {
#   name : string;
#   alive : bool;
#   age: int; 
# }

# func main() : void {
#   var koda: Dog;
#   var kippy: Dog;
#   koda = new Dog;
#   if(kippy != koda){ 
#     print("Checking"); 
#   }
# }
    
    
#     """
    
#     test_default_return = """
#         func main() : void { print(foo()); print(bar());
# }
# func foo() : int { return; /* returns 0 */
# }
# func bar() : bool { print("bar");
# }  /* returns false*/
#     """
    
#     test_spec_coercio = """
#         func main() : void { print(5 || false); var a:int;
# a = 1;
# if (a) {
# print("if works on integers now!");
# }
# foo(a-1); }
# func foo(b : bool) : void { print(b);
# }
    
#     """
    
#     test_cmp_void3 = """
#         func main() : void {
#   var b: bool;
#   b = foo() == nil;
# }

# func foo() : void {
#   var a: int;
# }

    
    
# #     """

# def main():
    
#     test_expr3 = """
#     func main(): void {
#         var a: bool;
#         a = !5;
#         print(a);
#     }
#     """
    
#     test_bad_nonstruct_access = """
#     struct p {
#         a:int;
#     }

#     func main(): void {
#         var x: int;
#         print(x.b);
#     }
            
#     """
    
#     test_bad_nonstruct_access2 = """
#     struct p {
#         a:int;
#     }

#     struct b {
#         asdf: int;
#     }

#     func main(): void {
#         var x: int;
#         x.b.a = 2;
#     }
#     """




# def main():
    
#     test_bad_struct_compare = """
#         struct circle{
#             r: int;
#         }

#         struct square{
#             s: int;
#         }

#         func main(): void{
#             var c: circle;
#             var s: square;
#             s = new square;
#             c = new circle;
#             print(c == s);
#         }
    
#     """





# def main():
    
#     test_coerce6= """
#     struct Dog {
#         name: string;
#         vaccinated: bool;
#     }

#     func main() : void {
#         var d: Dog;
#         d = new Dog;
#         d.vaccinated = 42;
#         print(d.vaccinated);
#     }
    
    
#     """
    
#     test_nil = """
#     struct s {
#   a:int;
# }

# func main() : int {
#   var x: s;
#   x = new s;
#   x = nil;
#   print(x.a);
# }
#     """
    
#     test_linked_list = """
#         struct node {
#     value: int;
#     next: node;
# }

# struct list {
#     head: node;
# }

# func create_list(): list {
#     var l: list;
#     l = new list;
#     l.head = nil;
#     return l;
# }

# func append(l: list, val: int): void {
#     var new_node: node;
#     new_node = new node;
#     new_node.value = val;
#     new_node.next = nil;

#     if (l.head == nil) {
#         l.head = new_node;
#     } else {
#         var current: node;
#         for (current = l.head; current.next != nil; current = current.next) {
#             /* It doesn't work in Barista if it's empty, so this is just a useless line */
#             print("placeholder");
#         }
#         current.next = new_node;
#     }
#     return;
# }

# func print_list(l: list): void {
#     var current: node;

#     if (l.head == nil) {
#         print("List is empty.");
#         return;
#     }

#     for (current = l.head; current != nil; current = current.next) {
#         print(current.value);
#     }
#     return;
# }

# func main(): void {
#     var l: list;
#     l = create_list();

#     append(l, 10);
#     append(l, 20);
#     append(l, 30);

#     print("Printing the list:");
#     print_list(l);

#     return;
# }
#     """
    
    
#     test_jennifer = """
#         struct Dog {
#   name : string;
#   alive : bool;
#   age: int; 
# }

# func main() : void {
#   var koda: Dog;
#   var kippy: Dog;
#   koda = new Dog;
#   if(kippy != koda){ 
#     print("Checking"); 
#   }
# }
#     """
    
#     test_compare_not = """
#         struct circle{
#   r: int;
# }

# struct square {
#   s: int;
# }


# func main(): void{
#   var c: circle;
#   var s: square;

#   s = new square;
#   c = new circle;
#   print(c != s);
# }
#     """

#     test_mario = """
#       struct A {x: 
#       int;}
# struct B {x: 
# int;}

# func main(): void {
#   getA();
#   return;
# }

# func getA() : A {
#   var b: B;
#   b = nil;
#   return b;
# }
    
#     """
    
#     test_operand_on_struct = """
#     struct A {
#         x: int;
#       }
      
#     func main(): void {
#         getA();
#     return;
#     }
    
    
#     """




# def main():
    
    
#     test_type_coercion = """
#         func main() : void {
#     print(5 == true);  
#     print(0 == false);
#     print(-1 == true);  
#     print(true != 0);  
# }
#     """
    
#     test_nill = """
#     struct Box {
#     weight: int;
# }

# func main() : void {
#     var b: Box;
#     b = new Box;  
#     print(b == nil);  
#     print(b != nil);  
# } 
#     """
    
#     test_field = """
#     struct Engine {
#         horsepower: int;
#     }

#     struct Car {
#         make: string;
#         engine: Engine;
#     }

#     func main() : void {
#         var car: Car;
#         car = new Car;
#         car.engine = new Engine; 
#         print(car.engine == nil);
#     }
#     """
    
#     test_nested_struct_referece_compaarison = """
#     struct Engine {
#         horsepower: int;
#     }

#     struct Car {
#         engine: Engine;
#     }

#     func main() : void {
#         var car1: Car;
#         var car2: Car;
#         car1 = new Car;
#         car1.engine = new Engine;
#         car2 = new Car;
#         car2.engine = car1.engine;  
#         print(car1.engine != car2.engine);  
#     }
#     """
    
#     test_invalid_coercion = """
#         func main() : void {
#             print(5 != print("hello"));
#         }
#     """
    
#     test_cmp_nil = """
#     func main() : void {
#          print(5 != nil);
#     }
#     """
    
    
    
    
#     # Struct Comparison by Reference
#     test_struct_comparison = """
#         struct Node {
#     value: int;
# }

# func main() : void {
#     var n1: Node;
#     var n2: Node;
#     n1 = new Node;
#     n2 = new Node;
#     print(n1 == n2);
#     n2 = n1;
#     print(n1 == n2);  
# }
#     """
    
 
    
#     test_ret2 = """
#         struct A {x: 
#         int;}
# struct B {x: 
# int;}

# func main(): void {
#   getA();
#   return;
# }

# func getA() : A {
#   var b: B;
#   b = nil;
#   return b;
# }
#     """
    
#     test_struct4 = """
#     struct a {
#   inner: a;
# }

# func main() : void {
#   var a : a;
#   print(a.inner);
# }
#     """
    
#     test_struct_nil = """
# struct Box {
#     weight: int;
# }

# func main() : void {
#     var b: Box;
#     print(b == nil);  
#     print(b != nil); 
# }
#     """
    
#     test_compare_nill = """
#         struct Person {
#     name: string;
# }

# func main() : void {
#     var p: Person;
#     print(p == nil);  
#     p = new Person;
#     print(p == nil);  
# }
#     """
    
    
        
#     test_coerce_5 = """
#     struct Circle {
#         radius: int;
#     }

#     func main() : void {
#         var c: Circle;
#         c = new Circle;
#         c.radius = 5;
#         print(c != 5); 
#     }
#     """
    
#     test_yolo = """
# struct Engine {
#     horsepower: int;
# }

# struct Car {
#     make: string;
#     engine: Engine;
# }

# func main() : void {
#     var car: Car;
#     car = new Car; 
#     print(car.engine == nil);  
# }
    
#     """
    
#     test_int_nil = """
#         func main() : void {
#     var x: int;
#     x = 5;
#     print(x == nil); 
# }
    
#     """
    
#     test_assigned = """
#         struct Node {
#     value: int;
# }

# func main() : void {
#     var n1: Node;
#     var n2: Node;
#     n1 = nil;  
#     n2 = new Node;  
#     print(n1 == nil);  
#     print(n2 == nil); 
#     print(n1 == n2);  
# }
    
#     """
    
#     test_challenge_2 = """
#     struct node {
#   value: int;
#   next: node;
# }

# func main(): void {
#   var root: node;
#   var here: node;
#   root = new node;
#   here = root;
#   root.value = 21;
#   var i: int;
#   for (i = 20; i; i = i - 1) {
#     here = insert_node(here, i);
#   }

#   for (here = root; here != nil; here = here.next) {
#     print(here.value);
#   }
#   return;
# }

# func insert_node(nd: node, val: int): node {
#   var new_nd: node;
#   new_nd = new node;
#   new_nd.value = val;
#   nd.next = new_nd;
#   return new_nd;
# }
    
    
#     """
    
#     test_strc_cmp4 = """
#     struct dog {
#  name : string;
# }
# func main() : void {
#  var a : dog;
#  var b : dog;
#  print(a == b);
# }
    
#     """
    
#     test_random_coerce = """
#     func main() : void {
#         var x: bool;
#         x = !5;
#         print(x);
#     }
            
#     """
    
#     test_random_nil = """
#         struct A {
#             a: int;
#         }

#         func main(): void {
#         var a: A;
#         a = new A;
#         a = f2();
#         /* prints nil */
#         print(a);
#         }

#         func f2(): A {
#         return nil;
#         }
    
#     """
    
#     test_struct4 = """
#         struct a {
#             name : string;
#         }
#         struct b {
#             a: a;
#         }

#         func main() : void {
#             var b : int;
#             b.a.name = "test";
#         }
#         """
        
#     test_mario1 = """
#         func main() : void {
#   var vd: bool;
#   vd = false;
#   if (true) {
#     var i: int;
#     for (i = 0; i - 10; i = i + 1) {
#       var x: int;
#       x = i * i - 7 * i + 10;
#       if (!x) {
#         vd = x;
#         print("is zero:    ", i, " -> ", x);
#       } else {
#         if (x < 0) {
#           print("below zero: ", i, " -> ", x);
#         } else {
#           print("above zero: ", i, " -> ", x);
#         }
#       }
#     }
#   }
# }
    
    
#     """
        
        
#     test_mario2 = """
# func main(): void {
#     direct_print();
#     assign_var();
#     print_rets();
#     return;
# }

# func direct_print(): void {
#   print(-0);
#   print(-1);
#   print(!1);
#   print(!0);
#   print(!!-1);
#   print(!!false);
#   print(!false);
#   print(!!true);
#   print(!true);
# }

# func assign_var() : void {
#   var i: int;
#   i = 6;
#   var b: bool;
#   b = i;
#   i = 0;
#   print(b);
#   b = -2;
#   print(b);
#   b = 1 / 2;
#   print(b);
# }

# func print_rets() : void {
#   print(ret_bool(4));
#   print(ret_bool(0));
#   print(ret_bool(-20));
#   print(impl_ret());
#   print(!impl_ret());
# }

# func ret_bool(a: int) : bool {
#   return a;
# }

# func impl_ret() : bool {
#   var a: int;
# }

# func bool_expr() : bool {
#   var a: int;
# }
    

#     """
    
#     test_mario3 = """
#     func main() : void {
#         print(1 + print());
#     }

#     """
#     test_mario_simple = """
# struct A {
#     b: B;
# }

# struct B {
#     c: int;
# }

# func main() : void {
#     var a: A;
#     a = new A;
#     a.b = new B;
#     print(a.b.c);  
# }
#     """








# def main():

# #     test_mario_simple = """
# # struct A {
# #     b: B;
# # }

# # struct B {
# #     c: int;
# # }

# # func main() : void {
# #     var a: A;
# #     a = new A;
# #     a.b = new B;
# #     print(a.b.c);  
# # }
# #     """
    
# # test_struct4 = """
# #         struct a {
# #             c : bool
# #         }
# #         func test(s : a) : a{
# #             return s;
# #         }
# #         func main(): void {
# #             var b: a;
# #             b = new a;
# #             b.c = false;
# #             b = test(b);
# #             print(b.c.a);
            
# #         }
# #     """
    
#     test_mario5 = """
#     struct X {
#         i: int; 
#         b: bool; 
#         s:string;
#     }
#     struct Y {
#         i: int; 
#         b: bool;
#         s:string;
#     }
#     struct Z {
#         x: X; 
#         y: Y; 
#         z: Z;
#     }

#     func main(): void {
#   var v: Z;
#   v = new Z;
#   setZ(v, 42, true, "marco");
#   v.z.z.z.z = nil;
#   print("v.x.i: ", v.x.i);
#   print("v.x.b: ", v.x.b);
#   print("v.x.s: ", v.x.s);
#   print("v.y.i: ", v.y.i);
#   print("v.y.b: ", v.y.b);
#   print("v.y.s: ", v.y.s);
#   print(v.z.z.z.z.y.b);
# }

#     func setZ(v: Z, i: int, b: bool, s:string): void {
#         v.z = v;
#         v.x = new X;
#         v.y = new Y;
#         v.z.z.z.z.z.z.x.i = i;
#         v.x.b = b;
#         v.z.z.z.z.x.s = s;
#         v.z.z.z.z.z.z.y.i = 100 - i;
#         v.y.b = !b;
#         v.z.z.z.z.y.s = s + " polo";
#     }
#     """
    
#     test_validity_nil = """
#         func main() : void {
#             var a: string;
#             a = five();
#             print("should not print");
#         }   
#         func five(): string {
#             return nil;
#         }
#     """
    
#     test_dog = """
#     struct flea {
#         age: int;
#         infected : bool;
#     }

#     struct dog {
#         name: string;
#         vaccinated: bool;
#         companion: flea;
#     }

# func main() : void {
#   var d: dog;
#   d = new dog;   /* sets d object reference to point to a dog structure */

#   print(d.vaccinated); /* prints false - default bool value */
#   print(d.companion); /* prints nil - default struct object reference */

#   /* we may now set d's fields */
#   d.name = "Koda";
#   d.vaccinated = true;
#   d.companion = new flea;
#   d.companion.age = 3;
# }
#     """

#     test_void_in_expression = """
#         func main() : void {
#     var x: int;
#     x = add(5, 10) + printHello();
# }

# func add(a: int, b: int) : int {
#     return a + b;
# }

# func printHello() : void {
#     print("Hello, Brewin++!");
# }
#     """

#     test_validity_nil = """
#         func main() : void {
#   var a: string;
#   a = five();
#   print("should not print");
# }

# func five(): string {
#   return nil;
# }
#     """
    
#     test_struct44 = """
#     struct a {
#         c : bool;
#     }

#     func test(s : a) : a {
#         return s;
#     }
#     func main() : void {
#         var b: a;
#         b = new a;
#         b.c = false;
#         b = test(b);
#         print(b.c.a);
#     }
#     """
    
#     test_anoush = """
#        func main() : void {
#     print(!1); 
#     } 
        
#     """
    
#     test_struc444 = """
#     struct node {
#     value: int;
#     next: node;
# }

# struct list {
#     head: node;
# }

# func create_list(): list {
#     var l: list;
#     l = new list;
#     l.head = nil;
#     return l;
# }

# func append(l: list, val: int): void {
#     var new_node: node;
#     new_node = new node;
#     new_node.value = val;
#     new_node.next = nil;

#     if (l.head == nil) {
#         l.head = new_node;
#     } else {
#         var current: node;
#         for (current = l.head; current.next != nil; current = current.next) {
#             /* It doesn't work in Barista if it's empty, so this is just a useless line */
#             print("placeholder");
#         }
#         current.next = new_node;
#     }
#     return;
# }

# func print_list(l: list): void {
#     var current: node;

#     if (l.head == nil) {
#         print("List is empty.");
#         return;
#     }

#     for (current = l.head; current != nil; current = current.next) {
#         print(current.value);
#     }
#     return;
# }

# func main(): void {
#     var l: list;
#     l = create_list();

#     append(l, 10);
#     append(l, 20);
#     append(l, 30);

#     print("Printing the list:");
#     print_list(l);

#     return;
# }
#     """
    
#     test_void = """
#     func main() : void {
#     printHello();  
# }

# func printHello() : void {
#     print("Hello, Brewin++!");
#     return 42;  
# }
    
#     """
    
#     test_void2 = """
#     func main() : void {
#     doNothing();  
# }

#     func doNothing() : void {
#         return nil;  
#     }
    
#     """
    
#     test_void3 = """
    
#     func main() : void {
#     checkSomething();  
# }

# func checkSomething() : void {
#     return true;  
# }
    
    
#     """
    
#     test_void4 = """
#     func main() : void {
#     sayHello();
# }

# func sayHello() : void {
#     print("Hello, Brewin++!");
#     return;  
# }
#     """
    
#     test_void5 = """
#     func test() : void {
#         return;
#     }
#     func main() : void {
#         print(test());
#     }
#     """
    
#     test_challenge1 = """
#         struct list {
#     val: int;
#     next: list;
# }

# func cons(val: int, l: list) : list {
#     var h: list;
#     h = new list;
#     h.val = val;
#     h.next = l;
#     return h;
# }

# func rev_app(l: list, a: list) : list {
#     if (l == nil) {
#         return a;
#     }

#     return rev_app(l.next, cons(l.val, a));
# }

# func reverse(l: list) : list {
#     var a: list;

#     return rev_app(l, a);
# }

# func print_list(l: list): void {
#     var x: list;
#     var n: int;
#     for (x = l; x != nil; x = x.next) {
#         print(x.val);
#         n = n + 1;
#     }
#     print("N=", n);
# }

# func main() : void {
#     var n: int;
#     var i: int;
#     var l: list;
#     var r: list;

#     n = inputi();
#     for (i = n; i; i = i - 1) {
#         var n: int;
#         n = inputi();
#         l = cons(n, l);
#     }
#     r = reverse(l);
#     print_list(r);
# }

    
#     """
    
#     test_void5 = """
#     func test() : void {
#         return;
#     }
#     func main() : void {
#         print(test());
#     }
#     """
    
#     test_struct4444 = """
# struct a {
#   name : string;
# }
# struct b {
#   a: a;
# }

# func main() : void {
#   var b : b;
#   b = new b;
#   b.a.name = "test";
# }
#     """
    
#     interpreter = Interpreter()
#     interpreter.run(test_struct4444)
#     # interpreter.run(test_invalid_param)
#     # interpreter.run(test_nil3)
#     # interpreter.run(test_unknown_type_1)
#     #interpreter.run(test_random_spec2)

# if __name__ == "__main__":
#     main()
    
    
    
    
    
# test Mario testcases 
# test correctness tests
    
# def main():
    
#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/Unit_Tests_V3/tests"
    
#     interpreter = Interpreter()

#     # Loop through all files in the specified directory
#     for filename in sorted(os.listdir(directory)):
#         file_path = os.path.join(directory, filename)
#         if os.path.isfile(file_path):
#             print(f"Processing file: {filename}")
#             with open(file_path, "r") as file:
#                 content = file.read()
#                 # Run the interpreter on the file content
#                 interpreter.run(content)
#             print()
            
            
# if __name__ == "__main__":
#     main()


# #tests incorrectness tests Mario

# def main():
#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/Unit_Tests_V3/fails"
    
#     interpreter = Interpreter()

#     # Loop through all files in the specified directory
#     for filename in sorted(os.listdir(directory)):
#         file_path = os.path.join(directory, filename)
#         if os.path.isfile(file_path):
#             print(f"Processing file: {filename}")
#             with open(file_path, "r") as file:
#                 content = file.read()
#                 try:
#                     # Run the interpreter on the file content
#                     interpreter.run(content)
#                 except Exception as e:
#                     # Log the error and continue with the next file
#                     print(f"Error processing file {filename}: {e}")
#             print()

# if __name__ == "__main__":
#     main()
    
    

    
    
    
# test correctness tests
    
# def main():
    
#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/v3/tests"
    
#     interpreter = Interpreter()

#     # Loop through all files in the specified directory
#     for filename in sorted(os.listdir(directory)):
#         file_path = os.path.join(directory, filename)
#         if os.path.isfile(file_path):
#             print(f"Processing file: {filename}")
#             with open(file_path, "r") as file:
#                 content = file.read()
#                 # Run the interpreter on the file content
#                 interpreter.run(content)
#             print()
            
            
# if __name__ == "__main__":
#     main()
    
    
# tests incorrectness tests

# def main():
#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/v3/fails"
    
#     interpreter = Interpreter()

#     # Loop through all files in the specified directory
#     for filename in sorted(os.listdir(directory)):
#         file_path = os.path.join(directory, filename)
#         if os.path.isfile(file_path):
#             print(f"Processing file: {filename}")
#             with open(file_path, "r") as file:
#                 content = file.read()
#                 try:
#                     # Run the interpreter on the file content
#                     interpreter.run(content)
#                 except Exception as e:
#                     # Log the error and continue with the next file
#                     print(f"Error processing file {filename}: {e}")
#             print()

# if __name__ == "__main__":
#     main()






# Test testcases toShare


# def main():
    
#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/testcasesTOSHARE"
    
#     interpreter = Interpreter()

#     # Loop through all files in the specified directory
#     for filename in sorted(os.listdir(directory)):
#         file_path = os.path.join(directory, filename)
#         if os.path.isfile(file_path):
#             print(f"Processing file: {filename}")
#             with open(file_path, "r") as file:
#                 content = file.read()
#                 try:
#                     # Run the interpreter on the file content
#                     interpreter.run(content)
#                 except Exception as e:
#                     # Log the error and continue with the next file
#                     print(f"Error processing file {filename}: {e}")
#             print()

# if __name__ == "__main__":
#     main()


#test correctness 200

# def main():

#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/200-test/tests"
    
#     interpreter = Interpreter()

#     # Loop through all files in the specified directory
#     for filename in sorted(os.listdir(directory)):
#         file_path = os.path.join(directory, filename)
#         if os.path.isfile(file_path):
#             print(f"Processing file: {filename}")
#             with open(file_path, "r") as file:
#                 content = file.read()
#                 # Run the interpreter on the file content
#                 interpreter.run(content)
#             print()
            
            
# if __name__ == "__main__":
#     main()


#tests incorrectness 200

# def main():
#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/200-test/fails"
    
#     interpreter = Interpreter()

#     # Loop through all files in the specified directory
#     for filename in sorted(os.listdir(directory)):
#         file_path = os.path.join(directory, filename)
#         if os.path.isfile(file_path):
#             print(f"Processing file: {filename}")
#             with open(file_path, "r") as file:
#                 content = file.read()
#                 try:
#                     # Run the interpreter on the file content
#                     interpreter.run(content)
#                 except Exception as e:
#                     # Log the error and continue with the next file
#                     print(f"Error processing file {filename}: {e}")
#             print()

# if __name__ == "__main__":
#     main()







# def main():

#     # test coer6 
#     test_corece6 = """
#     func check_flag(flag: bool) : void {
#         print(flag);
#     }

#     func main() : void {
#         var n: int;

#         n = 10;
#         check_flag(n);

#         n = 0;
#         check_flag(n);
#     }
#     """
    
#     test_easy = """
#         func check_flag(flag: int) : void {
#         print(flag);
#     }

#     func main() : void {
#         var n: int;
#         n = 10;
#     }
    
#     """
    
#     test_ret0 = """
#     func main(): void {
#         print("a");
#         return;
#         print("b");
# }
#     """


#     test_struct2 = """
# struct person {
#     name: string;
# }

# func main() : void {
#     var p: person;
#     p = new person;
#     print(p.age);
# }
    
#     """
    
    
#     test_struct5 = """
    
# struct x {
#     val:int;
# }

# struct y {
#     val:int;
# }

# func main() : void {
#     var a: x;
#     var b: y;
#     a = new y;
# }
    
    
#     """
    
#     test_no_main = """
# func Main(): void {
#   var a: int;
#   a = 5 + 10;
#   print(a);  
# }
# """
    
#     test_ret0 = """
#     func main(): void {
#         print("a");
#         return;
#         print("b");
# }
#     """
    
#     test_paul = """
#     func main() : void {
#         var a : int;
#         print(a.b);
# }
#     """
    
#     test_paul2 = """
    
#     func main() : void {
#         var a : int;
#     a.b = 5;
# }
#     """
    
# # test_hello = """
# #     func main() : void{
# #         print("hello");
# #         }
# #     """

#     test_ret0 = """
#     func main(): void {
#         print("a");
#         return;
#         print("b");
# }
#     """
    
#     test_chall2 = """
#         struct node {
#     value: int;
#     next: node;
# }

# struct list {
#     head: node;
# }

# func create_list(): list {
#     var l: list;
#     l = new list;
#     l.head = nil;
#     return l;
# }

# func append(l: list, val: int): void {
#     var new_node: node;
#     new_node = new node;
#     new_node.value = val;
#     new_node.next = nil;

#     if (l.head == nil) {
#         l.head = new_node;
#     } else {
#         var current: node;
#         for (current = l.head; current.next != nil; current = current.next) {
#             /* It doesn't work in Barista if it's empty, so this is just a useless line */
#             print("placeholder");
#         }
#         current.next = new_node;
#     }
#     return;
# }

# func print_list(l: list): void {
#     var current: node;

#     if (l.head == nil) {
#         print("List is empty.");
#         return;
#     }

#     for (current = l.head; current != nil; current = current.next) {
#         print(current.value);
#     }
#     return;
# }

# func main(): void {
#     var l: list;
#     l = create_list();

#     append(l, 10);
#     append(l, 20);
#     append(l, 30);

#     print("Printing the list:");
#     print_list(l);

#     return;
# }
    
#     """
    
#     test_connor = """
#         struct animal {
# name : string;
# extinct : bool;
# ears: int;
# }
# func main() : void {
# var pig : animal;
# var ret: bool;
# var hm : animal;
# ret = is_extinct(pig);
# print(ret);
# pig = new animal;
# pig.extinct = true;
# ret = is_extinct(pig);
# print(ret);
# hm = destroy_animals("pig", pig);
# print(pig.extinct);
# print(hm);

# }
# func is_extinct(p : animal) : bool {
# if (p == nil){
# print("i go in here first");
# return 0;
# }
# else{
# return p.extinct;
# }
# }
# func destroy_animals(name: string, p : animal) : animal{
# if (p==nil){
# p = new animal;
# }
# name = inputs("What animal do you want to destroy?");
# p.name = name;
# p.extinct = true;
# print("Destroyed animal ", p.name);
# return nil;
# }
#     """
    
#     test_ethan = """
#     struct a {
#   name : string;
# }
# struct b {
#   a: a;
# }

# func main() : void {
#   var b : b;
#   b = new b;
#   b.a.name = "test";
# }
    
#     """
    
    
#     test_olive = """
#     struct node {
#   value: int;
#   next: node;
# }

# func main(): void {
#   var root: node;
#   var here: node;
#   root = new node;
#   here = root;
#   root.value = 21;
#   var i: int;
#   for (i = 20; i; i = i - 1) {
#     here = insert_node(here, i);
#   }

#   for (here = root; here != nil; here = here.next) {
#     print(here.value);
#   }
#   return;
# }

# func insert_node(nd: node, val: int): node {
#   var new_nd: node;
#   new_nd = new node;
#   new_nd.value = val;
#   nd.next = new_nd;
#   return new_nd;
# }
    
#     """
    
#     test_call22 = """
#         struct maybe_int {
#   present : bool;
#   val : int;
# }

# struct tree {
#   left : tree;
#   right : tree;
#   val : maybe_int;
# }

# func definitely_int(value : int) : maybe_int {
#   var ret : maybe_int;
#   ret = new maybe_int;
#   ret.present = true;
#   ret.val = value;
#   return ret;
# }

# func new_tree() : tree {
#   var ret : tree;
#   ret = new tree;
#   ret.val = new maybe_int;
#   return ret;
# }

# func new_tree(root : int) : tree {
#   var ret : tree;
#   ret = new tree;
#   ret.val = definitely_int(root);
#   return ret;
# }

# func insert_sorted(root: tree, value : int) : void {
#   if (!root.val.present) {
#     root.val = definitely_int(value);
#   } else {
#     if (value <= root.val.val) {
#       if (root.left == nil) {
#         root.left = new_tree(value);
#       } else {
#         insert_sorted(root.left, value);
#       }
#     } else {
#       if (root.right == nil) {
#         root.right = new_tree(value);
#       } else {
#         insert_sorted(root.right, value);
#       }
#     }
#   }
# }

# func get_size(root : tree) : int {
#   if (root == nil) {
#     return 0;
#   }
#   var sum : int;
#   if (root.val.present) {
#     sum = 1;
#   }
#   return sum + get_size(root.left) + get_size(root.right);
# }

# func get_item(root : tree, index : int) : maybe_int {
#   var offset : int;
#   offset = get_size(root.left);
#   if (index < offset) {
#     return get_item(root.left, index);
#   }
#   if (root.val.present) {
#     if (index == offset) {
#       return root.val;
#     }
#     offset = offset + 1;
#   }
#   if (root.right == nil) {
#     return new maybe_int;
#   }
#   return get_item(root.right, index - offset);
# }

# func main () : void {
#   var list : tree;
#   list = new_tree();
#   insert_sorted(list, 5);
#   insert_sorted(list, 1);
#   insert_sorted(list, 3);
#   insert_sorted(list, 4);
#   insert_sorted(list, 11);
#   insert_sorted(list, 8);
#   insert_sorted(list, 6);

#   var i : int;
#   for (i = 0; true; i = i + 1) {
#     var result : maybe_int;
#     result = get_item(list, i);
#     if (!result.present) {
#       return;
#     }
#     print(result.val);
#   }
# }
# """
    
#     test_maybe = """
    
#     func maybe_return(n: int): int {
# if (n > 10) {
# return n;
# }
# return nil;

# }

# func main():void{
# print(maybe_return(5));
# }
    
#     """
    
#     test_ret0 = """
#     func main(): void {
#         print("a");
#         return;
#         print("b");
# }
#     """
    
#     test_unary = """
# struct Light {
#     isOn: bool;
# }

# func main() : void {
#     var l: Light;
#     l = new Light;
#     l.isOn = true;
#     print(!l.isOn);  
# }
#     """
    
#     test_call22 = """
#         struct maybe_int {
#   present : bool;
#   val : int;
# }

# struct tree {
#   left : tree;
#   right : tree;
#   val : maybe_int;
# }

# func definitely_int(value : int) : maybe_int {
#   var ret : maybe_int;
#   ret = new maybe_int;
#   ret.present = true;
#   ret.val = value;
#   return ret;
# }

# func new_tree() : tree {
#   var ret : tree;
#   ret = new tree;
#   ret.val = new maybe_int;
#   return ret;
# }

# func new_tree(root : int) : tree {
#   var ret : tree;
#   ret = new tree;
#   ret.val = definitely_int(root);
#   return ret;
# }

# func insert_sorted(root: tree, value : int) : void {
#   if (!root.val.present) {
#     root.val = definitely_int(value);
#   } else {
#     if (value <= root.val.val) {
#       if (root.left == nil) {
#         root.left = new_tree(value);
#       } else {
#         insert_sorted(root.left, value);
#       }
#     } else {
#       if (root.right == nil) {
#         root.right = new_tree(value);
#       } else {
#         insert_sorted(root.right, value);
#       }
#     }
#   }
# }

# func get_size(root : tree) : int {
#   if (root == nil) {
#     return 0;
#   }
#   var sum : int;
#   if (root.val.present) {
#     sum = 1;
#   }
#   return sum + get_size(root.left) + get_size(root.right);
# }

# func get_item(root : tree, index : int) : maybe_int {
#   var offset : int;
#   offset = get_size(root.left);
#   if (index < offset) {
#     return get_item(root.left, index);
#   }
#   if (root.val.present) {
#     if (index == offset) {
#       return root.val;
#     }
#     offset = offset + 1;
#   }
#   if (root.right == nil) {
#     return new maybe_int;
#   }
#   return get_item(root.right, index - offset);
# }

# func main () : void {
#     var list : tree;
    
#     var i : int;
#     for (i = 0; i < 5; i = i + 1) {
#         var result : maybe_int;
#         print("HEllo");
#   }
# }
# """

#     interpreter = Interpreter()
#     interpreter.run(test_call22)
#     # interpreter.run(test_invalid_param)
#     # interpreter.run(test_nil3)
#     # interpreter.run(test_unknown_type_1)
#     #interpreter.run(test_random_spec2)

# if __name__ == "__main__":
#     main()

    
    