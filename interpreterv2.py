from intbase import InterpreterBase, ErrorType
from brewparse import parse_program

# Interpreter class derived from interpreter base class
class Interpreter(InterpreterBase):
    
    def __init__(self, console_output=True, inp=None, trace_output=False):
        # call InterpreterBase's constructor
        super().__init__(console_output, inp)
        # call stack will keep track of functions using a last in first out approach, each dict keeps track of things like variables, e.g., a dict that maps variable names to their current value (e.g., { "foo" → 11 })
        self.call_stack = [] 
        # store function names in a dictionary
        self.func_name_to_ast = dict()
        
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
        self.run_func(main_func_node, [])
        
        
    # custon tracker is a dictionary that keeps track of function names
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
        local_scope = dict()        
        
        for arg_var_name,arg_value in zip(func_node.dict['args'], args):
            # Note we can pass in an expression as an arg value (ex: -1)
            evaluated_arg_avalue = self.do_evaluate_expression(arg_value)
            local_scope[arg_var_name.dict['name']] = evaluated_arg_avalue
        
        # get current func's inner level (aka the list of dictionaries)
        
        # call_stack is our global variable that keeps track of function scopes
        # We push the functions local_scope onto the stack
        self.call_stack.append([local_scope])
        
        # Execute each statement inside the function
        for statement in func_node.dict['statements']:
            # result is the return statment
            result = self.run_statement(statement)
            # note a function can return nil so its techincally returning something (ex: return nil; or return;)
            if (result == "nil"):
                return None
            # we have a return statement in the function
            if (result != None):
                # note return has handled popping from stack so need for popping here
                return result
        
        # we dont have something to return (so we just pop scope)
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
            expression = "return with no value"
            return expression
        
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
        # we have found the variable
        else:
            # get expression node
            expression = statement_node.dict['expression']
            
            # call do_evaulate_expression which handles the expression (ex: x = 5 + 6;)
            resulting_value = self.do_evaluate_expression(expression)
        
            # set the value to its corresponding vairble in dict
            dictionary_scope[variable_name] = resulting_value

            
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
        
        # case where we have a variable (x = y)
        elif expression.elem_type == 'var':
            # If an expression refers to a variable that has not yet been defined, then you must generate an error of type ErrorType.NAME_ERROR by calling InterpreterBase.error()
            
            # check if the varuabke was defined at all
            for dict in reversed(self.current_scope()):
                if expression.dict['name'] in dict:
                    # return variable value
                    return dict.get(expression.dict['name'])
            
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
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            
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
            operand2_value = self.do_evaluate_expression(operand2)
            
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
            operand2_value = self.do_evaluate_expression(operand2)
            
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
            operand2_value = self.do_evaluate_expression(operand2)
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
            # if both the operands are of type bool
            if isinstance(operand1_value, bool) and isinstance(operand2_value, bool):
                # compare operands
                return operand1_value or operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )     
    
    # Citation: The following code was found on Chatgpt
    
    def current_scope(self):
        # Return the current scope (top of the stack) (the scope is an a list of dictonaries, every dictionary corresponds to the functions scope and if/for loop scopes in that function)
        return self.call_stack[-1] 
    
    # End of citation
                    
#Main for testing purposes      
#     program_source = """func main(){
#                         var x;
#                         x = 5 + 6;
#                         print("The sum is: ", x);
#                     }"""
                    
#     test_input_no_arg_program = """func main() {
#                                     var b; 
#                                     b = inputi();
#                                     print(b);
#                                 }"""
    
#     test_input_arg_program = """func main() {
#                                     var b; 
#                                     b = inputi("Enter a number: ");
#                                     print(b);
#                                 }"""
                            
#     test_spec_example = """func main() {
#                             /* this is a comment */
#                             var first;
#                             var second;
#                             first = inputi("Enter a first #: ");
#                             second = inputi("Enter a second #: ");
#                             var sum;
#                             sum = (first + second);
#                             print("The sum is ", sum, "!");
#                         }"""
                        
#     test_var = """ func main(){
#                         var first;
#                         var second;
#                         first = 5; 
#                         second = first + 1 - 3;
#                         var third;
#                         third = (x + (5 - 3)) - y;
#                         print("The sum is ", third, "!");
#                 }"""
                
#     random_test = """
#                 func main(){
#                     var y;
#                     y = 2;
#                     var x;
#                     x = 3;
#                     print(y," is 1 plus ", x);
#                 }
#                 """
                
#     test_spec1 = """
#                 func main() {
#                     var a;
#                     a = 5 + 10;
#                     print(a);
#                     print("that's all!");
#                 }"""
                
#     test_spec2 = """
#                 func main() {
#                     var foo;
#                     foo = inputi("Enter a value: ");
#                     print(foo);
#                 }
#                 """
                
#     test_spec3 = """func main() {
#                     var bar;
#                     bar = 5;
#                     print("The answer is: ", (10 + bar) - 6, "!");
#                 }"""
                
#     test = """func main(){
#                 var x;
#                 x = "";
#                 print(x);
#             }"""
            
#     test1 = """
#             func main() {
#             print("Hello, world!");
#             }
#             """
            
#     test2 = """ func main() {
#             var x;
#             var y;
#             x = 7;
#             y = 3;
#             print("Sum: ", x + y);
#             print("Difference: ", x - y);          
#             }"""
            
#     test3 = """
#             func main() {
#                 print(x); 
#             }
#             """
                         
#     test4 = """ func main() {
#                     var result;
#                     result = (5 + 3) - (2 + 1);
#                     print("Result: ", result);
#                 }"""  
    
#     test5 = """
#                 func main() {
#                 var age;
#                 age = inputi("Enter your age: ");
#                 print("Your age is: ", age);
#             }
#             """
            
#     test6 = """
#                 func main() {
#                     var x;
#                     var x;
#                 }
#             """
    
#     test7 = """
#             func main() {
#             var x;
#             x = "hello" + 5;
#         }
#             """
    
#     test8 = """
#                 func main() {
#                 unknown_function();  
#             }
#             """
    
#     test9 = """
#             func main() {
#             var x;
#             print(x);  
#         }"""
        
#     # guranteed to have a at least one statement
#     test10 = """
#             func main() {
                
#             }
#             """
            
#     test11 = """
#             func main() {
#             var x;
#             x = ((5 + (6 - 3)) - ((2 - 3) - (1 - 7)));
#             print("Result: ", x);
#             }
#     """
    
#     test12 = """
#             func main() {
#                 var first;
#                 var second;
#                 first = inputi("Enter first number: ");
#                 second = inputi("Enter second number: ");
#                 print("Sum: ", first + second);
#                 }
#             """
            
#     test13 = """
#             func main() {
#                 var x;
#                 x = y + 5; 
#             }
#             """
            
#     test14 = """
#             func main() {
#                 var x;
#                 x = inputi("Enter a large number: ");
#                 print("You entered: ", x);
#             }
#             """
            
#     test15 = """
#             func main() {
#                 print("Line 1");
#                 print("Line 2");
#                 print("Line 3");
#                 print("Line 4");
#                 print("Line 5");
#             }
#             """
            
#     ######################### Project 2 Tests ##################################
    
#     # should print 120
#     test1_p2 = """ 
#                 func main() { 
#                     print(fact(5));
#                 }
#                 func fact(n) {
#                     if (n <= 1) { return 1; } return n * fact(n-1);
#                 }
#                 """
                
#     # should print 3
#     #              2
#     #              1
#     test2_p2 = """
#                 func main() {
#                     var i;
#                     for (i = 3; i > 0; i = i - 1) {
#                     print(i); 
#                     }
#                 }
#                 """
                
#     test_multiplication = """
#                     func main() {
#                         var x;
#                         var y;
#                         x = 7;
#                         y = 3;
#                         print("Sum: ", x * y);
#                     }
#                     """
    
#     test_division = """
#                     func main() {
#                         var x;
#                         var y;
#                         x = 5;
#                         y = 3;
#                         print("Sum: ", x / y);
#                     }
#                     """
                    
#     test_unary = """
#                     func main() {
#                         var x;
#                         x = -5;
#                         print("Sum: ", x);
#                     } 
#                 """
    
#     test_concatenate = """
#                         func main() {
#                             print("abc" + "def");
#                         } 
#                         """
#     # test ==                  
#     test_comparison_equals = """
#                             func main() {
#                                print(5 < 5);
#                                print(5 < 6);
#                                var a;
#                                a = 5;
#                                print(6 <= 5);
#                                var b;
#                                b = 3;
#                                print(b > 5);
#                                print (5 >= 5);
                               
                               
#                                var c;
#                                var d;
#                                var e;
#                                c = true;
#                                d = false;
#                                e = true;
#                                print (c == d);
#                                print (c == e);
                               
#                                print (c != d);
#                                print (c != e);
                               
#                             } 
#                             """
                            
#     test_unary = """
#                     func main() {
#                         print(-6);
#                         print(!true);
#                     }
#                 """
    
#     test_logical_binary_operators = """
#                                     func main() {
#                                         print(true || false);
#                                         print(true || false && false);
#                                         print(true && false);
#                                     }
#                                     """
                                    
#     test_if_statement = """
#                         func foo(c) {
#                             if (c == 10) {
#                                 c = "hi";  /* reassigning c from outer-block */
#                                 print(c);  /* prints "hi" */
#                             }
#                             print(c); /* prints “hi” */
#                         }
#                         func main() { 
#                             foo(10);
#                         }
#                         """
    
#     test_if = """
#         func main() {
#             var x;
#             x = 15;

#             if (x > 10) {
#                 print("Greater");
#             } 
#             else {
#                 print("Smaller");
#             }

#             if (x < 10) {
#                 print("This won't print");
#             }
#         }
#             """
            
#     test_bad_expr1 = """
#                     func main() {
#                         var a;
#                         a = true + 5;
#                     }
#                     """
                    
#     test = """
#             func main() {
#                 print(unknown_var);
#             }
#             """
            
#     test_simple_func_call = """
#                             func foo() {
#                                 print("hello world!");
#                             }
#                             func main() {
#                                 foo();
#                             }
#                             """
    
#     test_func_call_with_args = """
#                             func bletch(a,b,c) {
#                                 print("The answer is: ", a+b*c);
#                             }

#                             func main() {
#                                 bletch(1,2,3);
#                             }
#                             """
                            
     
               
#     test_for = """
#                 func main() {
#                     var i;
#                     for (i=0; i < 5; i=i+1) {
#                         print(i);
#                     }
#                 }     
#                 """
                
#     test_static_scoping_1 = """
#         func main() {
#             var a;
#             a = 5;
#             if (true) {
#                 print(a);
#                 var a;
#                 a = "foo";
#                 print(a);
#             }
#             print(a);
#         }
#     """
    
#     test_static_scoping_simple = """
#         func main() {
#             var a;
#             a = 5;
#             if (true) {
#                 print(a);
#             }
#         }
#     """

#     test_return = """
#                 func foo(x) {
#                     if (x < 0) {
#                         print(x);
#                         return -x;
#                         print("this will not print");
#                     }
#                 print("this will not print either");
#                 return 5*x;
#                 }
#                 func main() {
#                     print("the positive value is ", foo(-1));
#                 }
#                 """
                
#     test_print = """
#                 func main() {
#                     var x;
#                     x = 1;
#                     print(x);
#                 }
#                 """
                
                          
#     test_fact = """
#                 func main() { 
#                     print(fact(5));
#                 }
#                 func fact(n) {
#                     if (n <= 1) { 
#                     return 1; 
#                     } 
#                     return n * fact(n-1);
#                 }
#                 """
                
#     test_5 = """
#             func bar(a) { print(a);
#             }
#             func main() { bar(5);
#             bar("hi");
#             bar(false || true);
#             }
#             """
            
#     test_6 = """
#             func bletch(a,b,c) {
#                 print("The answer is: ", a+b*c);
#             }
#             func main() 
#             { 
#                 bletch(1,3,2+4);
#             }
#             """
            
#     test_spec = """
#                 func foo(a) { 
#                     print(a);
#                 }
#                 func foo(a,b) {
#                     print(a," ",b);
#                 }
#                 func main() { 
#                     foo(5);
#                     foo(6,7);
#                 }
#                 """
                
#     test_spec_10 = """
#                 func foo() {
#                     print("hello"); /* no explicit return command */
#                 }
#                 func bar() {
#                     return; /* no return value specified */
#                 }
                
#                 func main() { 
#                     var val;
#                     val = nil;
#                     if (foo() == val && bar() == nil) { 
#                         print("this should print!"); 
#                     } 
#                 }
#                     """
                    
#     test_spec_11 = """
#                     func main() { 
#                         var val;
#                         val = nil;
#                         if (val == nil) { 
#                             print("this should print!"); 
#                         } 
#                     }
#                     """
                    
#     test_inputs = """
#                 func main() {
#                     var b; 
#                     b = inputi("Hello");
#                     print(b);
#                 }
#             """
            
#     test_nil = """
#             func foo() {
#                 print(1);
#             }

#             func bar() {
#                 return nil;
#             }

#             func main() {
#                 var x;
#                 x = foo();
#                 if (x == nil) {
#                     print(2);
#                 }
#                 var y;
#                 y = bar();
#                 if (y == nil) {
#                     print(3);
#                 }
#             }
#                 """
                
#     test_nil2  = """
    
#                 func foo() {
#                     print(1);
#                 }
                
#                 func bar() {
#                     return nil;
#                 }
                
#                 func main() {
#                     var x;
#                     x = foo();
#                     if (x == nil) {
#                         print(2);
#                     }
#                     var y;
#                     y = bar();
#                 }
    
#                 """
                
#     test_compare = """
#             func main() {
#                 print(1 >= 1);
#                 print(1 == "1");
#                 print(1 == true); 
#                 print(1 == nil);

#                 print("----");

#                 print("1" == 1);
#                 print("1" == "1");
#                 print("1" == true);
#                 print("1" == nil);

#                 print("----");

#                 print(true == 1); 
#                 print(true == "1");
#                 print(true == true); /*issue*/
#                 print(true == nil);

#                 print("----");

#                 print(nil == 1);
#                 print(nil == "1");
#                 print(nil == true);
#                 print(nil == nil);
#             }
#             """
            
#     test_compare_1 = """
#                     func main() {
#                         print(true == true); /*issue*/
#                     }

#                     """
                    
#     test_spec_1000 = """
#     func foo(a) { print(a);
# }
# func foo(a,b) { print(a," ",b);
# }
# func main() { foo(5);
# foo(6,7); }
#                     """
                    
#     test_spec_1001 = """
#                 func foo() {
# print("hello");
# /* no explicit return command */
# }
# func bar() {
# return; /* no return value specified */
# }
# func main() { var val;
# val = nil;
# if (foo() == val && bar() == nil) { print("this should print!"); } }
#                     """
                    
#     test_spec_1002 = """
#     func foo(x) {
#   if (x < 0) {
#     print(x);
#     return -x;
#     print("this will not print");
#   }
#   print("this will not print either");
#   return 5*x;
# }
# func main() {
#   print("the positive value is ", foo(-1));
# }"""

#     test_for_loop = """
#                     func main() {
#                         var i;
#                         for (i = 3; i > 0; i = i - 1) {
#                         print(i); 
#                         }
#                     }
#                     """
                    
                    
#     test_nil_cmp = """
#                 func d() {
#                     print("hello");
#                 }

#                 func main() {
#                     print(nil == 5);
#                     print(d() != nil); /* should be false */
#                 }
#                     """
                    
#     test_spec_string = """ 
#     func main() {
#     var foo;
#     foo = inputs("Enter a value: ");
#     print(foo);
#     }
#     """
    
#     test_nested_for = """
#                         func main() {
#                     var x;
#                     var q;
#                     for (x = 0; x < 3; x = x + 1) {
#                         for (q = 0; q < 2; q = q + 1) {
#                         print(q*q);
#                         }
#                     }
#                     }
#                     """
                    
#     test_nested_ret = """
#     func foo(a) {
#   if (a != 1) {
#     if (a != 2) {
#       var i;
#       for (i = 0; i < 15; i = i + 1) {
#         if (i == a) {
#           return "oh";
#         }
#       }
#     }
#   }
# }

# func loop1() {
#   return loop2();
# }
# func loop2() {
#   return loop3();
# }

# func loop3() {
#   return 5;
# }

# func main() {
#   var a;
#   a = 10;
  
#   print(foo(a));
#   print(loop1());
# }
#     """
    
#     test_compare_more = """
#                 func main () {
#                     print("1" != 1);
#                     print(true != 1);

#                 }
#                         """
                        
                        
#     test_compare = """
#             func main() {
#                 print(1 >= 1);
#                 print(1 == "1");
#                 print(1 == true); 
#                 print(1 == nil);

#                 print("----");

#                 print("1" == 1);
#                 print("1" == "1");
#                 print("1" == true);
#                 print("1" == nil);

#                 print("----");

#                 print(true == 1); 
#                 print(true == "1");
#                 print(true == true); /*issue*/
#                 print(true == nil);

#                 print("----");

#                 print(nil == 1);
#                 print(nil == "1");
#                 print(nil == true);
#                 print(nil == nil);
#             }
#             """

#     test_random = """
#     func main() {
#         var x;
#     for (x=0; x < 2; x = x+1) {
#         var x;
#         x = -1;
#         print(x);
#     }
#     print(x);
#     }
#                        """
                       
#     test_if_return = """
#         func foo(c) { 
#             if (c == 10) {
#                 return 5;
#             }
#             else {
#                 return 3;
#             }
#         }

#         func main() {
#             print(foo(10));
#             print(foo(11));
#         }
#         """
        
#     testrandom3 = """
# func main() {
#   var s;
#   var n;
#   s = inputs();
#   n = inputi();

#   print(s == n);
#   print(s == nil);
#   print(n == nil);
#   print(s == "1");

#   print(s != n);
#   print(s != nil);
#   print(n != nil);
#   print(s != "1");

# }


#                 """

######################################### Proj 2 Test Cases 

# def main():

#     test_static_scoping = """
# func foo(c) { 
#   if (c == 10) {
#     c = "hi";  /* reassigning c from the outer-block */
#     print(c);  /* prints "hi" */
#   }
#   print(c); /* prints “hi” */
# }

# func main() {
#   var c;
#   c = 10;
#   foo(c);
#   print(c);
# }
#     """
    
#     test_bad = """
#             func main() {
#                 print("Hello");
#                 return true >= true;
#             }
#                 """
                
    
    
#     test_ret_11 = """
#         func main() {
#             var x;
#             x = 5;
#             if (x == 5) {
#                 print("Inside if pre return");
#                 return;
#                 print("Inside if post return");
#             }
#             print("Outside if");
#         }
#          """
         
        
#     test_dup = """
#             func main() { 
#              var a;
#              var a;
#         }
    
    
    
#                 """
                
                
#     test_factorial = """
#         func main() {
#   print(fact(5));
# }

# func fact(n) {
#   if (n <= 1) { return 1; }
#   return n * fact(n-1);
# }
#         """


####################### proj 3 test cases ##########################

# def main():
    
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
#                 }
#                 """
                       
#     interpreter = Interpreter()
#     interpreter.run(test_print)


# if __name__ == "__main__":
#     main()
    
    
    # import os
    # directory = '/Users/ricardovarelatellez/Downloads/v2/tests'

    # # Loop through all files in the specified directory
    # for filename in os.listdir(directory):
    #     file_path = os.path.join(directory, filename)
    #     if os.path.isfile(file_path):
    #         print(f"Processing file: {file_path}")
    #         with open(file_path, 'r') as file:
    #             content = file.read()
    #             # Run the interpreter on the file content
    #             interpreter.run(content)  
          
    #interpreter.run(test_compare)
            

        
  
        
# def main():
#     interpreter = Interpreter()
    
#     with open('./test.br', 'r') as f:
#         program = f.read()
        
#     interpreter.run(program)
    
# if __name__ == '__main__':
#     main()

