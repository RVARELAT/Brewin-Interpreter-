from intbase import InterpreterBase, ErrorType
from brewparse import parse_program

# class for creating 'lazy value' 
class LazyValue:
    def __init__(self, expression, environment):
        # ex: f(3) + 2
        self.expression = expression
        # capture environment
        self.environment = environment
        # will help wite chaching the value
        self.has_been_evaluated = False
    # getters
    def get_lazyValue_expression(self):
        return self.expression
    def get_lazyValue_environment(self):
        return self.environment
    def get_lazyValue_status(self):
        return self.has_been_evaluated
    # setters
    def set_lazyValue_expression(self, new_value):
        self.expression = new_value
    def set_has_been_evaluated(self):
        self.has_been_evaluated = True
    
    # closure 
    def value(self):
        # evaluate value if it hasn't been evaluated
        if self.has_been_evaluated == False:
            result = self.environment.do_evaluate_expression(self.expression)
            while isinstance(result, LazyValue):
                result = result.value()
            self.cache_value = result
            self.has_been_evaluated = True
        return self.cache_value   

# Interpreter class derived from interpreter base class
class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False):
        # call InterpreterBase's constructor
        super().__init__(console_output, inp)
        # call stack will keep track of functions using a last in first out approach, each dict keeps track of things like variables, e.g., a dict that maps variable names to their current value (e.g., { "foo" → 11 })
        self.call_stack = [] 
        # store function names in a dictionary
        self.func_name_to_ast = {}
        
    # The Interpreter is passed in a program as a list of strings that needs to be interpreted
    def run(self, program):
        # parse program into AST
        ast = parse_program(program)
        # set up a function tracker that keeps track of the func names
        self.set_up_function_tracker(ast)
        # look for the main function node in AST (will throw error if no main found)
        if ("main", 0) not in self.func_name_to_ast:
            super().error(ErrorType.NAME_ERROR, "Function main not found")
        # get the main func node
        main_func_node = self.func_name_to_ast[("main", 0)]
        
        # call run func on main function node (remember main func has no args so we say None)
        result = self.run_func(main_func_node, [])
        
        # check if we have an exception 
        if (type(result) == dict) and result["type"] == "exception":
            # we have an exception that was never caught after being propogated
            super().error(ErrorType.FAULT_ERROR, f"exception not caught anywhere ")
            
        
    # custom tracker is a dictionary that keeps track of function names
    def set_up_function_tracker(self, ast):
        # loop through function Nodes
        for func_def in ast.dict['functions']:
            name = func_def.dict['name']
            # 'args' which maps to a list of Argument nodes
            number_of_params = len(func_def.dict['args'])
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
        local_scope = {}  
        
        for arg_var_name,arg_value in zip(func_node.dict['args'], args):
            # Note we can pass in an expression as an arg value (ex: -1)
            lazyValue_environment = [dict_ref.copy() for dict_ref in self.current_scope()]
            local_scope[arg_var_name.dict['name']] = LazyValue(arg_value, lazyValue_environment)
        
        # call_stack is our global variable that keeps track of function scopes
        # We push the functions local_scope onto the stack
        self.call_stack.append([local_scope])
    
        result_returned = False
        # note a statement can now throw raise an exception
        # Execute each statement inside the function
        for statement in func_node.dict['statements']:
            # result is the return statment
            result = self.run_statement(statement)
            
            # toss the return of a solo func call in main
            if (func_node.dict["name"] == "main" and result != None and statement.elem_type == 'fcall') and type(result) != dict: 
                continue
            
            # check if we have an exception and propogate
            if type(result) == dict:
                if result["type"] == "exception":
                    # don't pop if its a return div by zero as popping was already handled
                    if result["exception_type"] == "div0":
                        return result
                    
                    # careful when we have a return with an exception
                    if (statement.elem_type != 'return'):
                        self.call_stack.pop()    
                    return result
            # note a function can return nil so its techincally returning something (ex: return nil; or return;)
            if (result == "nil"):
                result_returned = True
                return None
            # we have a return statement in the function
            if (result != None):
                # note return has handled popping from stack so need for popping here
                result_returned = True
                return result
        # we only pop from stack if no return was encountered
        if result_returned == False:
            self.call_stack.pop()      
        # must return nil
        return None
    
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
            return self.do_func_call(statement_node)
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
        # is a raise statement
        elif statement_node.elem_type == 'raise':
            return self.do_raise_statement(statement_node)
        # is a try block
        elif statement_node.elem_type == 'try':
            return self.do_try_statement(statement_node)
        
    # try block
    def do_try_statement(self, try_node):
        # Variables defined within the try block are not accessible in the corresponding catch clauses.
        # create a local scope for try block
        local_scope = {}
        self.current_scope().append(local_scope)
            
        result = None
        # run the statements try block
        for statement in try_node.dict['statements']:
            result = self.run_statement(statement)
            
            # check if we encountered a raise statement 
            if type(result) == dict and result["type"] == "exception":
                # handle the exception later
                break 
            
            # check if we have a regular result
            if result != None:
                # return func handles the popping for stack
                return result
                
        # pop try block scope
        self.current_scope().pop()    
        
        # check if there was an exception in try block
        if type(result) == dict and result["type"] == "exception":
            # get the exception type
            exception_type = result["exception_type"]
            # try block has 'catchers'
            for catch_node in try_node.dict['catchers']:
                # check if we have a catcher for the exception
                if exception_type == catch_node.dict['exception_type']:
                    # local scope for variables in catch block
                    local_scope = {}
                    self.current_scope().append(local_scope)
                    # we have found a catcher so run statements in catcher
                    for statement in catch_node.dict['statements']:
                        catch_block_result = self.run_statement(statement)
                        if catch_block_result != None:
                            # return handles pop
                            return catch_block_result
                    # we have finished running the statements in the catch node
                    self.current_scope().pop()
                    return None
            # If no matching catch clause is found in the current try block, the exception propagates to the innermost enclosing try block, then the next innermost enclosing try block, etc., and then to the calling function. (also maybe its a super.error())
            return result
        # no exceptions and no return
        return None
        
    # raise statement
    def do_raise_statement(self, raise_statement):
        # raise statement has an expression type (eagerly evaluate it)
        exception_type = self.do_evaluate_expression(raise_statement.dict['exception_type'])
        # exception_type must be a string, if not throw error
        if (type(exception_type) is not str):
            super().error(ErrorType.TYPE_ERROR, "expression_type of raise is not a string")
        else:
            # Citation: this idea of using a dict for exceptions was acquired from perplexity.ai
            # return an exception to propogate up (as a dictionary form)
            return {"type": "exception", "exception_type": exception_type}
            # End of citation
    
    # return statement
    def do_return_statement(self, statement_node):
        # get the expression
        expression = statement_node.dict['expression'] 
        # first check if the return value is None (ex: return;)
        if expression == None:
            expression = "return with no value"
            return expression
        # 'expression' which maps to an expression, variable or constant to return or None (if the return statement returns a default value of nil)
        # do_evaluate expression will handle the cases above
        evaluated_expression = self.do_evaluate_expression(expression)
        
        # this means we had a 'return nil;' So we technically return something
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
            local_scope = {}
            self.current_scope().append(local_scope)
            # check if the condition of the for loop does not evaluate to a boolean
            is_condition = self.do_evaluate_expression(statement_node.dict['condition'])
            
            # check if condition of for loop raised an exception
            if (type(is_condition) == dict and is_condition["type"] == "exception"):
                return is_condition
            # condition is not a boolean
            if isinstance(is_condition, bool) == False:
                            super().error(
                        ErrorType.TYPE_ERROR,
                        "condition of the for loop does not evaluate to a boolean"
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
            # update the condition and check if its true (eagerly evaluate)
            self.do_assignment(statement_node.dict['update'])
        
        
    def do_if_statement(self, statement_node):
        # the expression/variable/value that is the condition of the if statement must evaluate to a boolean
        is_it_bool = self.do_evaluate_expression(statement_node.dict['condition'])
        
        #check if the condition of if statement threw an exception
        if (type(is_it_bool) == dict and is_it_bool["type"] == "exception"):
            return is_it_bool
        
        if isinstance(is_it_bool, bool) == False:
            super().error(ErrorType.TYPE_ERROR, "condition of the if statement does not evaluate to a boolean")
            
        # condition maps to a boolean expression, variable or constant that must be True for the if statement to be executed
        if (is_it_bool == True):
            # we need a new scope for if statement
            local_scope = {}
            self.current_scope().append(local_scope)
            # eun statemnts in if statement
            for statement in statement_node.dict['statements']:
                # result is the return statment (in case we have return in if statement)
                result = self.run_statement(statement)
                # if the return statement inside the if statment did return with no return value (ex: return;)
                if result == "return with no value":
                    self.call_stack.pop()
                    return "nil"
                # we have finished executing function so we can return (return handles the popping off the stack)
                if (result != None):
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
                local_scope = {}
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
            # add the variable def to the last dictionary in list of dictionaries (name as key and None as default value)
            self.current_scope()[-1][statement_node.dict['name']] = None
    
    # assign value to variable     
    def do_assignment(self, statement_node):
        # get the name of the variable (ex: 'x')
        variable_name = statement_node.dict['name']
        # verify that variable name is in scope
        in_scope = False
        dictionary_scope = None
        for dict in reversed(self.current_scope()):
            if variable_name in dict:
                # we save the dictionary where this variable name is located
                dictionary_scope = dict
                in_scope = True
                # as soon as we find the first dict that has this variable we break
                break
        
        # variable name not in scope
        if in_scope == False:
            super().error(ErrorType.NAME_ERROR, f"Variable {variable_name} has not been defined",
            )
        # we have found the variable
        else:
            # get expression node
            expression = statement_node.dict['expression']
            # create a special copy of the environment (dictionaries are shallow copied)
            lazyValue_environment = [dict_ref.copy() for dict_ref in self.current_scope()]
            # set the value to its corresponding variable in dict and        create a lazy value for the right side
            dictionary_scope[variable_name] = LazyValue(expression, lazyValue_environment)
            
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
            #print("HEY", self.do_evaluate_print_call(func_node))
            return self.do_evaluate_print_call(func_node)
        else:
            # verify the func defnition exists
            function = self.get_func_by_name_and_param_len(func_node.dict['name'], len(func_node.dict['args']))
            # remeber args you pass in to functions can be expressions (ex: foo(n-1); this is handle by run_func)
            # pass in the function defintion and then pass in the arg values
            return self.run_func(function, func_node.dict['args'])
            
            
    # evaluate the print call (actually output what print wants to print)
    def do_evaluate_print_call(self, print_node):
        string_to_output = ""
        # nothing to print so return nil (none)
        if (print_node.dict['args']) == None:
            return None
        # loop through arguments of print statement
        for argument in print_node.dict['args']:
            # check if the argument is a bool so we can make it lowercase
            expression_value = self.do_evaluate_expression(argument)
            # handle exceptions from print statements
            if (type(expression_value) == dict and expression_value["type"] == "exception"):
                return expression_value
            # make bool lowercase
            if (isinstance(expression_value, bool)):
                lowercase_bool = str(expression_value)
                string_to_output += lowercase_bool.lower()
            else:
                string_to_output += str(expression_value)
        # output using the output() method in our InterpreterBase base class (output() method automatically appends a newline character after each line it prints, so you do not need to output a newline yourself.)
        super().output(string_to_output)
        
    # get the user input 
    def do_evaluate_input_call(self, input_node):
        # If an inputi() expression has more than one parameter passed to it, then you must generate an error of type ErrorType.NAME_ERROR by calling InterpreterBase.error()
        if len(input_node.dict['args']) > 1:
            super().error(ErrorType.NAME_ERROR, f"No inputi() function found that takes > 1 parameter")
        # If an inputi() function call has a prompt parameter, you must first output it to the screen using our InterpreterBase output() method before obtaining input from the user
        # assume that the inputi() function is invoked with a single argument, the argument will always have the type of string
        if len(input_node.dict['args']) == 1:
            input_prompt = self.do_evaluate_expression(input_node.dict['args'][0])
            
            # check if input prompt raised an exception
            if (type(input_prompt) == dict and input_prompt["type"] == "exception"):
                return input_prompt
            
            super().output(input_prompt)
        # the user wants to input a string
        if input_node.dict['name'] == 'inputs':
            user_string_input = super().get_input()
            return user_string_input
        # the user wants to input an integer
        user_input = int(super().get_input())
        return user_input
        
    
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
            return self.do_func_call(expression)
        
        # case where we have a variable ( x = 7)
        elif expression.elem_type == 'var':
            # check if the variable was defined at all
            for scope_dict in reversed(self.current_scope()):
                if expression.dict['name'] in scope_dict:
                    expression_value = scope_dict.get(expression.dict['name'])
                    
                    # check if var value is a lazy value
                    if isinstance(expression_value, LazyValue) == True:
                        # check if value has been cached
                        if (expression_value.get_lazyValue_status() == True):
                            return expression_value.get_lazyValue_expression()
                        
                        # get the expression of the lazy value
                        lazyvalue_expression = expression_value.get_lazyValue_expression()
                        
                        # push lazyValue environment onto stack
                        self.call_stack.append(expression_value.get_lazyValue_environment())
                        
                        # evaluate the lazy value 
                        lazyValue_value = self.do_evaluate_expression(lazyvalue_expression)
                        
                        # pop the lazy value environment
                        self.call_stack.pop()
                        
                        # update the expression and status in lazyvalue
                        expression_value.set_lazyValue_expression(lazyValue_value)
                        expression_value.set_has_been_evaluated()
                        
                        return lazyValue_value
                    
                    # expression is not a lazyValue (has been evaluated)
                    return expression_value
            
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
            # check if operand is exception
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            # check if operand is exception
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
            
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
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
            
            # in Brewin#, attempting to divide by zero during eager evaluation results in a "div0" exception being raised. This exception can be caught using a try/catch block.
            if operand2_value == 0:
                # create a div0 exception
                return {"type": "exception", "exception_type": "div0"}
                        
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
            # check if operand 1 throws an exception
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
            
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
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
            
                        
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
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
            
            # if both the operands are nil (None) return true
            if (operand1_value == None and operand2_value == None):
                return True
            
            # check that operands are the same type
            if type(operand1_value) != type(operand2_value):
                return False
            
            # if both the operands are of type int or type string or type bool
            if isinstance(operand1_value, int) and isinstance(operand2_value, int) or isinstance(operand1_value, str) and isinstance(operand2_value, str) or isinstance(operand1_value, bool) and isinstance(operand2_value, bool):
                return operand1_value == operand2_value
            else:
                # values of diff types safety check
                return False
        
        elif expression.elem_type == '!=':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
            
            # if both the operands are nil (None)
            if (operand1_value == None and operand2_value == None):
                return False
            
            # check that operands are the same type (needed for true != 1 or else 1 will be interpreted as true)
            if type(operand1_value) != type(operand2_value):
                return True
            
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
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand1_value
            
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
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
                        
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
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
                 
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
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
                        
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
            # short circuiting
            if isinstance(operand1_value, bool):
                # if one operand is false, whole thing is false
                if (operand1_value == False):
                    return False
                
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
                
            operand2_value = self.do_evaluate_expression(operand2)
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
            
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
            
            # short circuiting
            if isinstance(operand1_value, bool):
                # if one operand is true, whole thing is true
                if (operand1_value == True):
                    return True
            
            if type(operand1_value) == dict and operand1_value["type"] == "exception":
                return operand1_value
            
            operand2_value = self.do_evaluate_expression(operand2)
            
            if type(operand2_value) == dict and operand2_value["type"] == "exception":
                return operand2_value
            
            # if both the operands are of type bool
            if isinstance(operand1_value, bool) and isinstance(operand2_value, bool):
                # compare operands
                return operand1_value or operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )     
    
    # get the top of the stack
    def current_scope(self):
        # Return the current scope (top of the stack) (the scope is an a list of dictonaries, every dictionary corresponds to the functions scope and if/for loop scopes in that function)
        return self.call_stack[-1] 
    

##################### Proj 4 test cases #######################
                
# def main():   
    
#     ################### Short Circuiting #####################
#     test_short1 = """
# func t() {
#  print("t");
#  return true;
# }

# func f() {
#  print("f");
#  return false;
# }

# func main() {
#   print(t() || f());
#   print("---");
#   print(f() || t()); 
# }

#     """
    
#     test_basic_and = """
#     func t() {
#         print("t");
#         return true;
#     }

#     func f() {
#         print("f");
#         return false;
#     }

#     func main() {
#         print(t() && f());
#         print("---");
#         print(f() && t());
#     }
#     """
    
#     test_basic_or = """
#     func t() {
#   print("t");
#   return true;
# }

# func f() {
#   print("f");
#   return false;
# }

# func main() {
#   print(t() || f());
#   print("---");
#   print(f() || t());
# }
#     """
    
#     test_nested_and = """
#     func t() {
#   print("t");
#   return true;
# }

# func f() {
#   print("f");
#   return false;
# }

# func main() {
#   print(t() && (t() && f()));
# }
#     """
    
#     test_nested_or = """
#     func t() {
#   print("t");
#   return true;
# }

# func f() {
#   print("f");
#   return false;
# }

# func main() {
#   print(f() || (f() || t()));
# }
#     """
    
#     test_spec_short = """
#     func foo() {
#         print("foo");
#         return true; }
#     func bar() { 
#         print("bar"); 
#         return false;
#     }
#     func main() {
#         print(foo() || bar() || foo() || bar());
#         print("done");
#     } 
#     """
    
#     test_side_and = """
#     func increment(x) {
#   print("increment");
#   return false;
# }

# func isZero(x) {
#   print("isZero");
#   return x == 0;
# }

# func main() {
#   var x;
#   x = 0;
#   print(isZero(x) && increment(x)); 
# }
#     """
    
#     test_side_or = """
#     func increment(x) {
#   print("increment");
#   return false;
# }

# func isZero(x) {
#   print("isZero");
#   return x == 0;
# }

# func main() {
#   var x;
#   x = 1;
#   print(isZero(x) || increment(x)); 
# }
#     """
    
    
#     test_and_with_exception_in_second_operand = """
# func t() {
#   print("t");
#   return true;
# }

# func raiseError() {
#   raise "and_second_error";
#   return false;
# }

# func main() {
#   try {
#     print(t() && raiseError());
#   }
#   catch "and_second_error" {
#     print("Caught and_second_error");
#   }
# }
#     """   
    
#     test_or_with_exception_in_second_operand = """
#     func f() {
#   print("f");
#   return false;
# }

# func raiseError() {
#   raise "or_second_error";
#   return true;
# }

# func main() {
#   try {
#     print(f() || raiseError());
#   }
#   catch "or_second_error" {
#     print("Caught or_second_error");
#   }
# }  
#     """
    
#     test_exception_in_first_operand = """
# func raiseError() {
#   raise "first_operand_error";
#   return true;
# }

# func safeFunction() {
#   print("safeFunction executed");
#   return true;
# }

# func main() {
#   try {
#     print(raiseError() && safeFunction());
#   }
#   catch "first_operand_error" {
#     print("Caught first_operand_error");
#   }
# }
#     """
    
#     test_mixed_logical_operators = """
# func t() {
#   print("t");
#   return true;
# }

# func f() {
#   print("f");
#   return false;
# }

# func main() {
#   print((f() || t()) && (t() || f()));
# }
#     """
    
#     test_chained_logical_and = """
#         func t() {
#   print("t");
#   return true;
# }

# func f() {
#   print("f");
#   return false;
# }

# func main() {
#   print(t() && t() && f() && t());
# }
#     """
    
#     test_chained_logical_or = """
# func t() {
#   print("t");
#   return true;
# }

# func f() {
#   print("f");
#   return false;
# }

# func main() {
#   print(f() || f() || t() || f());
# }
#     """
    
#     ###################### EXCEPTIONS ##########################
    
#     # exception type not a string
#     test_excep_string = """
#     func main(){
#         try {
#             raise 1;
#         }
#         catch "error1" {
#             print("Caught error1");
#         }
#     }
#     """
    
#     #  Raise and Catch an Exception
#     test_basic_excep = """
#     func main() {
#         try {
#             raise "error1";
#         }
#         catch "error1" {
#             print("Caught error1");
#         }
#     }
#     """
    
#     test_minimal_raise = """
#     func main() {
#         raise "except1";
#     }
#     """
    
#     # In brewin, exceptions can propagate through functions
#     test_back_to_caller = """
#     func foo() {
#         print("F1");
#         raise "except1";
#         print("F3");
#     }

#     func main() {
#     try {
#         print("M1");
#         foo();
#         print("M2");
#     }
#     catch "except1" {
#         print("M3");
#     }
#     print("M5");
#     } """
    
#     test_fault_error = """
#     func foo() {
#         print("F1");
#         raise "except1";
#         print("F3");
#     }

#     func main() {
#     try {
#         print("M1");
#         foo();
#         print("M2");
#     }
#     catch "except2" {
#         print("M3");
#     }
#     print("M5");
#     }
#     """
    
#     test_propogate = """
#     func foo() {
#         try {
#             raise "z";
#         }
#         catch "x" {
#             print("x");
#         }
#         catch "y" {
#             print("y");
#         }
#         catch "z" {
#             print("z");
#             raise "a";
#         }
#         print("q");
#     }

#     func main() {
#         try {
#             foo();
#             print("b");
#         }
#         catch "a" {
#             print("a");
#         }
#     }
#     """
    
#     test_nested_exception_prop = """
#     func main() {
#         try {
#             try {
#                 raise "inner_error";
#             }
#             catch "unrelated_error" {
#                 print("Caught unrelated_error");
#             }
#         }
#         catch "inner_error" {
#             print("Caught inner_error");
#         }
#     }
#     """
    
#     test_except2 = """
#     func main() {
#         var r;
#         r = 10;
#         raise r;
#     }
#     /*
#     *OUT*
#     ErrorType.TYPE_ERROR
#     *OUT*
#     */
    
#     """
    
#     test_spec_ex = """
#     func foo() { 
#         print("F1"); 
#         raise "except1"; 
#         print("F3");
#     }
#     func bar() { 
#         try {
#             print("B1");
#             foo();
#             print("B2");
#         }
#         catch "except2" {
#             print("B3");
#         }
#     print("B4");
#     }
#     func main() { 
#         try {
#             print("M1");
#             bar();
#             print("M2");
#         }
#         catch "except1" {
#             print("M3");
#         }
#         catch "except3" { 
#             print("M4");
#         }
#     print("M5");
#     }
#     """
    
#     test_Combined_Try_Catch_with_Function_Calls = """
# func errorFunction() {
#   raise "error_from_function";
# }

# func safeFunction() {
#   return 42;
# }

# func main() {
#   try {
#     print(safeFunction());
#     errorFunction();
#     print("This will not be printed");
#   }
#   catch "error_from_function" {
#     print("Caught error from function");
#   }
# }
#     """
    
#     test_Execution_Flow_with_Exceptions = """
#     func main() {
#   print("Before try block");
#   try {
#     raise "execution_error";
#   }
#   catch "execution_error" {
#     print("Caught execution_error");
#   }
#   print("After try block");
# }
#     """
    
#     test_var_shadowing = """
# func main() {
#   var x;
#   x = 100;
#   try {
#     var x;
#     x = 200;
#     print(x);
#     raise "scope_error";
#   }
#   catch "scope_error" {
#     print(x);
#   }
# }  """
    
    
#     test_chat2 = """
# func raiseFirstError() {
#   raise "first_error";
#   return 0;
# }

# func raiseSecondError() {
#   raise "second_error";
#   return 0;
# }

# func main() {
#   try {
#     print(raiseFirstError() || raiseSecondError());
#   }
#   catch "first_error" {
#     print("Caught first_error");
#   }
#   catch "second_error" {
#     print("Caught second_error");
#   }
# }
#     """
    
#     test_div_by_zero = """
# func divide(a, b) {
#   return a / b;
# }

# func main() {
#   try {
#     var result;
#     result = divide(10, 0);
#     print(result);
#   }
#   catch "div0" {
#     print("Caught division by zero!");
#   }
# }
#     """
    
#     test_eh = """
#     func foo() {
#   print("F1");
#   raise "except1";
#   print("F3");
# }

# func bar() {
#  try {
#    print("B1");
#    foo();
#    print("B2");
#  }
#  catch "except2" {
#    print("B3");
#  }
#  print("B4");
# }

# func main() {
#  try {   print("M1");
#    bar();
#    print("M2");
#  }
#  catch "except1" {
#    print("M3");
#  }
#  catch "except3" {
#    print("M4");
#  }
#  print("M5");
# } 
#     """
    
#     test_chat3 = """
# func safeFunction() {
#   print("safeFunction executed");
#   return "safe_value";
# }

# func raiseError() {
#   raise "multiple_print_error";
#   return "error_value";
# }

# func main() {
#   try {
#     print(safeFunction());
#     print("Before exception", raiseError(), "After exception");
#     print("This should not execute");
#   }
#   catch "multiple_print_error" {
#     print("Caught multiple_print_error");
#   }
# }
#     """
    
#     test_except_cond1 = """
# func foo() {
#   raise "x";
#   print("foo");
#   return true;
# }

# func main() {
#   try {
#      if (foo()) {
#        print("true"); 
#      }
#   }
#   catch "x" {
#     print("x");
#   }
# }
#     """
    
#     test_condition = """
# func safeFunction() {
#   print("safeFunction executed");
#   return "safe_value";
# }

# func raiseError() {
#   raise "multiple_print_error";
#   return "error_value";
# }

# func main() {
#   try {
#     print(safeFunction());
#     print("Before exception", raiseError(), "After exception");
#     print("This should not execute");
#   }
#   catch "multiple_print_error" {
#     print("Caught multiple_print_error");
#   }
# }
#     """
    
    
    

# #################### lazy eval ###########################
  
#     test_lazy_simple_spec = """
#     func main() {
#         var result;
#         result = f(3) + 10;
#         print("done with call!");
#         print(result);  /* evaluation of result happens here */
#         print("about to print result again");
#         print(result);
#     }
#     func f(x) {
#         print("f is running"); 
#         var y;
#         y = 2 * x;
#         return y;
#     } """
    
#     test_basic_lazy = """
#     func lazyEval() {
#         print("Function called!");
#         return 42;
#     }

#     func main() {
#         var x;
#         x = lazyEval(); /* Function is not called here */
#         print("Before using x");
#         print(x);        /* Function is called here */
#         print(x);        /* Cached result is used here */
#     }   
#     """
    
#     test_error_during_lazy = """
#     func faultyFunction() {
#         return undefinedVar; /* Name error occurs here when evaluated */
#     }   

#     func main() {
#         var x;
#         x = faultyFunction(); /* No error yet */
#         print("Assigned x!"); /* This should print */
#         print(x);             /* Name error occurs here */
#     }
#     """
    
#     test_deferred_exception = """
#         func functionThatRaises() {
# raise "some_exception"; /* Exception occurs here when func is called */ return 0;
# }
# func main() {
# var result;
# result = functionThatRaises();
# print("Assigned result!");
# /* Exception will occur when result is evaluated */ print(result, " was what we got!");
# }
#     """
    
#     test_eager_in_if = """
#     func eagerEval() {
#     print("Eager evaluation!");
#     return true;
# }

# func main() {
#     if (eagerEval()) { /* Function is called here */
#         print("Condition met");
#     }
# }
#     """
    
#     test_eager_in_for = """
# func eagerEval(i) {
#     print("Eager evaluation for", i);
#     return i < 3;
# }

# func main() {
#     var i;
#     for (i = 0; eagerEval(i); i = i + 1) {
#         print("Loop iteration", i);
#     }
# }
#     """
    
#     test_lazy_cache1 = """
# func bar(x) {
#  print("bar: ", x);
#  return x;
# }

# func main() {
#  var a;
#  a = bar(0);
#  a = a + bar(1);
#  a = a + bar(2);
#  a = a + bar(3);
#  print("---");
#  print(a);
#  print("---");
#  print(a);
# }
#     """
    
#     test_lazy_cache11 = """
#     func main() {
#         var a;
#         a = 1;
#         a = a + 2;
#         print(a);
#     }
#     """
    
#     test_video = """
#         func f(x) {
#             print("f is running"); var y;
#             y = 2 * x;
#             return y;
#         }
#         func main() {
#             var x;
#             var result;
#             x = f(3);
#             result = x + 10;
#             print(x);
#             x = 4;
#             print(x);
#             print(result);
#         }
#     """
    
#     test_lazy_fcall1 = """
# func foo() {
#   print("foo");
#   return 4;
# }

# func main() {
#   foo();
#   print("---");
#   var x;
#   x = foo();
#   print("---");
#   print(x); 
# }
#     """
    
#     test_lazy_arg = """
# func op(a, b , c) {
#   if (c) {
#     return a * -b;
#   } else {
#     return a + b;
#   }
# }

# func param(a) {
#   print(a);
#   return a;
# }

# func main() {
#   print("enter main");
#   var x;
#   var y;
#   print("lazy evals");
#   x = op(param(5), param(7), param(true));
#   y = op(param(5), param(7), param(false));
#   print("exit main");
# }
#     """
    
#     test_except_chain2 = """

# func foo() {
#   print("foo");
#   foob();
#   print("a");
#   raise "a";
# }

# func foob() {
#   print("foob");
#   print(food());
#   print("b");
#   raise "b";
# }

# func food() {
#   print("food");
#   inputi(foot());
#   print("c");
#   raise "c";
# }

# func foot() {
#   print("foot");
#   return bar();
#   print("d");
#   raise "d";
# }

# func fool() {
#   print(1 + bar());
#   print("e");
#   raise "e";
# }

# func foop() {
#   print(!foom());
#   print("f");
#   raise "f";
# }

# func foom() {
#   print(-bar());
#   print("g");
#   raise "g";
# }

# func bar() {
#   print("bar");
#   raise "x";
# }

# func main() {
#   try {
#     foo();
#   }
#   catch "x" {
#     print("x");
#   }
# }
#     """
    
#     test_intro_except = """
# func foo() {
#   print("F1");
#   raise "except1";
#   print("F3");
# }

# func bar() {
#  try {
#    print("B1");
#    foo();
#    print("B2");
#  }
#  catch "except2" {
#    print("B3");
#  }
#  print("B4");
# }

# func main() {
#  try {
#    print("M1");
#    bar();
#    print("M2");
#  }
#  catch "except1" {
#    print("M3");
#  }
#  catch "except3" {
#    print("M4");
#  }
#  print("M5");
# }
#     """
    
    
#     test_lazy_fcall2 = """
# func foo(a, b, c) {
#   print(a + b);
# }

# func funny() {
#   print("funny");
#   return "funny";
# }

# func joke() {
#   print("joke");
#   return "joke";
# }

# func main() {
#   foo(funny(), joke(), x);
# }
#     """
    
#     test_lazy_fcall3 = """
# func foo(m) {
#   print(m);
#   var t;
#   t = -m;
#   return t;
# }

# func main() {
#   var x;
#   x = 1;
#   x = foo(x);
#   x = foo(x);

#   var y;
#   y = x;
#   print("final y: ", y);
#   print("final x: ", x);
# }
#     """
    
#     test_lazy_except_pain = """
# func foo() {
#   print("foo");
#   return bar();
# }

# func bar() {
#   print("bar");
#   raise "a";
# }

# func main() {
#   foo();
# }
#     """
    
#     test_lazy_unused_invalid_var = """
# func main() {
#   var a;
#   foo("entered function");
# }

# func foo(a) {
#   print(a);
#   var a;
# }
#     """
    
#     interpreter = Interpreter()
#     interpreter.run(test_lazy_unused_invalid_var)
    
# if __name__ == "__main__":
#     main()
    
    
    
# connor copy of cases

# def main():
    
#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/v4copy/tests"
    
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
    


#Connor correctness tests
    
# def main():
    
#     import os
#     directory = "/Users/ricardovarelatellez/Downloads/v4/tests"
    
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
