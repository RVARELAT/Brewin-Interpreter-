from intbase import InterpreterBase, ErrorType
from brewparse import parse_program

# Interpreter class derived from interpreter base class
class Interpreter(InterpreterBase):
    
    def __init__(self, console_output=True, inp=None, trace_output=False):
        # call InterpreterBase's constructor
        super().__init__(console_output, inp)
        # dict to track things like variables, e.g., a map that maps variable names to their current value (e.g., { "foo" → 11 })
        self.variable_tracker = dict()
        
    # The Interpreter is passed in a program as a list of strings that needs to be interpreted
    def run(self, program):
        # parse program into AST
        ast = parse_program(program)
        # The interpreter processes the Abstract Syntax Tree and locates the node that holds details about the main() function.
        main_func_node = self.get_main_func_node(ast)
        # no main found
        if (main_func_node == None):
            super().error(
                ErrorType.NAME_ERROR,
                "No main() function was found",
            )
        # call run func
        self.run_func(main_func_node)
        
        # print statement to keep track of dictionary
        #print("Dictionary", self.variable_tracker)
    
    def get_main_func_node(self, ast):
        # loop through functions in AST and find "main" 
        for function in ast.dict['functions']:
            # main found
            if function.dict['name'] == 'main':
                return function
        # no main found
        return None
        
    # Execute each statement inside the main function      
    def run_func(self, func_node):
        for statement in func_node.dict['statements']:
            self.run_statement(statement)
    
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
            
    # Add variable name to variable_tracker if possible (can't redefine it)
    def do_definition(self, statement_node):
        if statement_node.dict['name'] in self.variable_tracker:
            super().error(
                ErrorType.NAME_ERROR,
                f"variable {statement_node.dict['name']} defined more than once",
            )
        else:
            # add the variable name as a key to the dictionary of variables (None as default Value)
            self.variable_tracker[statement_node.dict['name']] = None
            
    def do_assignment(self, statement_node):
        # get the name of the variable (ex: 'x')
        variable_name = statement_node.dict['name']
        # You must verify that the variable being assigned (e.g., x in x = 5;) has been defined in the "var" statement
        if variable_name not in self.variable_tracker: 
            super().error(
                ErrorType.NAME_ERROR,
                f"Variable {variable_name} has not been defined",
            )
        else:
            # get expression node
            expression = statement_node.dict['expression']
            # call do_evaulate_expression which handles the expression (ex: x = 5 + 6, )
            resulting_value = self.do_evaluate_expression(expression)
            # assign the resulting_value to the corresponding variable in dict
            self.variable_tracker[variable_name] = resulting_value
            
    # determine which function is in the func node (print() found in statement nodes and inouti() found in expression nodes)
    def do_func_call(self, func_node):
        # only found in expression nodes
        # evaluate_input_call will help us get the user input
        if func_node.dict['name'] == 'inputi':    
            user_input = self.do_evaluate_input_call(func_node)
            return user_input
        elif func_node.dict['name'] == 'print':
            self.do_evaluate_print_call(func_node)
        else:
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {func_node.dict['name']} has not been defined",
            )
            
    # evaluate the print call (actually output what print wants to print)
    def do_evaluate_print_call(self, print_node):
        string_to_output = ""
        # loop through arguments of print statement
        for argument in print_node.dict['args']:
            string_to_output += str(self.do_evaluate_expression(argument))
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
            
        # the inputi() function has no prompt
        # get input from the user and get_input() method returns a string regardless of what the user types in, so you'll need to convert the result to an integer yourself.
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
        # case where we have an inputi() in an expression (only the case for proj 1)
        elif expression.elem_type == 'fcall':
            # do func call will determine that it should be an inputi()
            return self.do_func_call(expression)
        
        # case where we have a variable (x = y)
        elif expression.elem_type == 'var':
            # If an expression refers to a variable that has not yet been defined, then you must generate an error of type ErrorType.NAME_ERROR by calling InterpreterBase.error(),
            if expression.dict['name'] not in self.variable_tracker:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {expression.dict['name']} has not been defined",
                )
            # using the var_name (key), find the var in the dictionary
            # get will return the value of the key
            else:
                return self.variable_tracker.get(expression.dict['name'])

        # case where we add 
        elif expression.elem_type == '+':
            # get the two operands
            operand1 = expression.dict['op1']
            operand2 = expression.dict['op2']
            # get the operand values
            operand1_value = self.do_evaluate_expression(operand1)
            operand2_value = self.do_evaluate_expression(operand2)
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
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
            # if both the operands are of type int
            if isinstance(operand1_value, int) and isinstance(operand2_value, int):
                return operand1_value - operand2_value
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
                    
#Main for testing purposes      
def main():
    program_source = """func main(){
                        var x;
                        x = 5 + 6;
                        print("The sum is: ", x);
                    }"""
                    
    test_input_no_arg_program = """func main() {
                                    var b; 
                                    b = inputi();
                                    print(b);
                                }"""
    
    test_input_arg_program = """func main() {
                                    var b; 
                                    b = inputi("Enter a number: ");
                                    print(b);
                                }"""
                            
    test_spec_example = """func main() {
                            /* this is a comment */
                            var first;
                            var second;
                            first = inputi("Enter a first #: ");
                            second = inputi("Enter a second #: ");
                            var sum;
                            sum = (first + second);
                            print("The sum is ", sum, "!");
                        }"""
                        
    test_var = """ func main(){
                        var first;
                        var second;
                        first = 5; 
                        second = first + 1 - 3;
                        var third;
                        third = (x + (5 - 3)) - y;
                        print("The sum is ", third, "!");
                }"""
                
    random_test = """
                func main(){
                    var y;
                    y = 2;
                    var x;
                    x = 3;
                    print(y," is 1 plus ", x);
                }
                """
                
    test_spec1 = """
                func main() {
                    var a;
                    a = 5 + 10;
                    print(a);
                    print("that's all!");
                }"""
                
    test_spec2 = """
                func main() {
                    var foo;
                    foo = inputi("Enter a value: ");
                    print(foo);
                }
                """
                
    test_spec3 = """func main() {
                    var bar;
                    bar = 5;
                    print("The answer is: ", (10 + bar) - 6, "!");
                }"""
                
    test = """func main(){
                var x;
                x = "";
                print(x);
            }"""
            
    test1 = """
            func main() {
            print("Hello, world!");
            }
            """
            
    test2 = """ func main() {
            var x;
            var y;
            x = 7;
            y = 3;
            print("Sum: ", x + y);
            print("Difference: ", x - y);          
            }"""
            
    test3 = """
            func main() {
                print(x); 
            }
            """
                         
    test4 = """ func main() {
                    var result;
                    result = (5 + 3) - (2 + 1);
                    print("Result: ", result);
                }"""  
    
    test5 = """
                func main() {
                var age;
                age = inputi("Enter your age: ");
                print("Your age is: ", age);
            }
            """
            
    test6 = """
                func main() {
                    var x;
                    var x;
                }
            """
    
    test7 = """
            func main() {
            var x;
            x = "hello" + 5;
        }
            """
    
    test8 = """
                func main() {
                unknown_function();  
            }
            """
    
    test9 = """
            func main() {
            var x;
            print(x);  
        }"""
        
    # guranteed to have a at least one statement
    test10 = """
            func main() {
                
            }
            """
            
    test11 = """
            func main() {
            var x;
            x = ((5 + (6 - 3)) - ((2 - 3) - (1 - 7)));
            print("Result: ", x);
            }
    """
    
    test12 = """
            func main() {
                var first;
                var second;
                first = inputi("Enter first number: ");
                second = inputi("Enter second number: ");
                print("Sum: ", first + second);
                }
            """
            
    test13 = """
            func main() {
                var x;
                x = y + 5; 
            }
            """
            
    test14 = """
            func main() {
                var x;
                x = inputi("Enter a large number: ");
                print("You entered: ", x);
            }
            """
            
    test15 = """
            func main() {
                print("Line 1");
                print("Line 2");
                print("Line 3");
                print("Line 4");
                print("Line 5");
            }
            """
            
    ######################### Project 2 Tests ##################################
    
    # should print 120
    test1_p2 = """ 
                func main() { 
                    print(fact(5));
                }
                func fact(n) {
                    if (n <= 1) { return 1; } return n * fact(n-1);
                }
                """
                
    # should print 3
    #              2
    #              1
    test2_p2 = """
                func main() {
                    var i;
                    for (i = 3; i > 0; i = i - 1) {
                    print(i); 
                    }
                }
                """
                
    test_func_call_with_args = """
                        func bletch(a,b,c) {
                            print("The answer is: ", a+b*c);
                        }

                        func main() {
                            bletch(1,2,3);
                        }
                        """
                        
    test_return = """
                func foo(x) {
                    if (x < 0) {
                        print(x);
                        return -x;
                        print("this will not print");
                    }
                print("this will not print either");
                return 5*x;
                }
                func main() {
                    print("the positive value is ", foo(-1));
                }
                """
                
    test_for = """
            func main() {
                var i;
                for (i=0; i < 5; i=i+1) {
                    print(i);
                }
            }     
            """
                
            
    test_static_scoping_1 = """
        func main() {
            var a;
            a = 5;
            if (true) {
                print(a);
                var a;
                a = "foo";
                print(a);
            }
            print(a);
        }
    """
    
    test_static_scoping_simple = """
        func main() {
            var a;
            a = 5;
            if (true) {
                print(a);
            }
        }
    """
    
    test_return = """
                func foo(x) {
                    if (x < 0) {
                        print(x);
                        return -x;
                        print("this will not print");
                    }
                print("this will not print either");
                return 5*x;
                }
                func main() {
                    print("the positive value is ", foo(-1));
                }
                """
               
               
    interpreter = Interpreter()
    interpreter.run(test_p2)
            
if __name__ == "__main__":
    main()
        
        
        
# def main():
#     interpreter = Interpreter()
    
#     with open('./test.br', 'r') as f:
#         program = f.read()
        
#     interpreter.run(program)
    
# if __name__ == '__main__':
#     main()