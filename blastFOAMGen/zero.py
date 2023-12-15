from unittest.mock import patch


class ZeroGenerator:

    def get_filenames(self, phase_properties):
        files = []
        selectable_phases = ["explosive", "water", "air"]
        phases_selected = [phase for phase in selectable_phases if phase_properties[phase]['active']]

        types = ["rho"]
        if len(phases_selected) > 1:
            types.append("alpha")

        for type_ in types:
            for phase in phases_selected:
                files.append([phase, f"{type_}.{phase_properties[phase]['phaseName']}.orig"])

        return files


    def generate_alpha(self, file_type, phase_name, geometries):
        geometry_blocks = "\n".join(
            f"{geometry['fileString']['name']}\n      {{\n          type            zeroGradient;\n      }}"
            for geometry in geometries
        )
        internal_field_value = "1" if file_type == "water" else "0"
        return f"""
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       volScalarField;
            object      alpha.{phase_name}.orig;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
        
        dimensions      [0 0 0 0 0 0 0];
        
        internalField   uniform {internal_field_value};
        
        boundaryField
        {{
            #includeEtc "caseDicts/setConstraintTypes"
            {geometry_blocks}
            
            walls
            {{
                type            zeroGradient;
            }}
        
            "ball.*"
            {{
                type            zeroGradient;
            }}

            outlet
            {{
                type            zeroGradient;
            }}
        
            tank
            {{
                type            zeroGradient;
            }}
        }}
        
        // ************************************************************************* //
        """


    def generate_rho(self, phase_name, geometries, explosive_active, rho=None):
            if explosive_active:
                geometry_blocks = "\n".join(
                    f"{geometry['fileString']['name']}\n    {{\n        type            zeroGradient;\n    }}"
                    for geometry in geometries
                )
                rho_value = rho if rho is not None else "1.225"
                return f"""
                /*--------------------------------*- C++ -*----------------------------------*/
                FoamFile
                {{
                    version     2.0;
                    format      ascii;
                    class       volScalarField;
                    object      rho.{phase_name}.orig;
                }}
                // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
                
                dimensions      [1 -3 0 0 0 0 0];
                
                internalField   uniform {rho_value};
                
                boundaryField
                {{
                    #includeEtc "caseDicts/setConstraintTypes"
                    {geometry_blocks}
                    
                    walls
                    {{
                        type            zeroGradient;
                    }}

                    "ball.*"
                    {{
                        type            zeroGradient;
                    }}
                
                    outlet
                    {{
                        type            zeroGradient;
                    }}
                
                    tank
                    {{
                        type            zeroGradient;
                    }}
                }}
                
                // ************************************************************************* //
                """
            else:
                return f"""
                /*--------------------------------*- C++ -*----------------------------------*\
                | =========                 |                                                 |
                | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
                |  \\    /   O peration     | Version:  2.3.0                                 |
                |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
                |    \\/     M anipulation  |                                                 |
                \*---------------------------------------------------------------------------*/
                FoamFile
                {{
                    version     2.0;
                    format      ascii;
                    class       volScalarField;
                    object      rho.orig;
                }}
                // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

                dimensions      [1 -3 0 0 0 0 0];

                internalField   uniform 1.3;

                boundaryField
                {{
                    //- Set patchGroups for constraint patches
                    #includeEtc "caseDicts/setConstraintTypes"

                    {phase_name}
                    {{
                        type            zeroGradient;
                    }}
                }}
                """


    def generate_p(self, ambient, patch_name, explosive_active):
        if explosive_active:
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*/
            FoamFile
            {{
                version     2.0;
                format      ascii;
                class       volScalarField;
                object      p.orig;
            }}
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
            
            dimensions      [1 -1 -2 0 0 0 0];
            
            internalField   uniform {ambient['pressure']};
            
            boundaryField
            {{
                #includeEtc "caseDicts/setConstraintTypes"
            
                walls
                {{
                    type            zeroGradient;
                }}

                "ball.*"
                {{
                    type            zeroGradient;
                }}
            
                outlet
                {{
                    type            pressureWaveTransmissive;
                    value           $internalField;
                }}
            
                tank
                {{
                    type            zeroGradient;
                }}
            }}
            
            // ************************************************************************* //
            """
        else:
            return"""
            FoamFile
            {
                version     2.0;
                format      ascii;
                class       volScalarField;
                object      p.orig;
            }
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            dimensions      [1 -1 -2 0 0 0 0];

            internalField   uniform 112040;

            boundaryField
            {
                //- Set patchGroups for constraint patches
                #includeEtc "caseDicts/setConstraintTypes"

                "ball.*"
                {
                    type            zeroGradient;
                }
            }"""


    def generate_point(self, patchName, explosive_active):
        if explosive_active:
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*/
            FoamFile
            {{
                version     2.0;
                format      ascii;
                class       pointVectorField;
                object      pointDisplacement.orig;
            }}
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
            
            dimensions      [0 0 0 0 0 0 0];
            
            internalField   uniform (0 0 0);
            
            boundaryField
            {{
                #includeEtc "caseDicts/setConstraintTypes"

                walls
                {{
                    type            fixedValue;
                    value           $internalField;
                }}

                "ball.*"
                {{
                type            timeVaryingFixedDisplacement;
                value           $internalField;
                }}


                outlet
                {{
                    type            fixedValue;
                    value           $internalField;
                }}

                tank
                {{
                    type            timeVaryingFixedDisplacement;
                    value           $internalField;
                }}
            }}

            // ************************************************************************* //
            """
        else:
            return """
            FoamFile
            {
                version     2.0;
                format      ascii;
                class       pointVectorField;
                object      pointDisplacement.orig;
            }
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            dimensions      [0 0 0 0 0 0 0];

            internalField   uniform (0 0 0);

            boundaryField
            {
                //- Set patchGroups for constraint patches
                #includeEtc "caseDicts/setConstraintTypes"

                "ball.*"
                {
                    type            timeVaryingFixedDisplacement;
                    value           $internalField;
                }
            }

            // ************************************************************************* //
        """


    def generate_t(self, explosive_active):
        if explosive_active:
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*/
            FoamFile
            {{
                version     2.0;
                format      ascii;
                class       volScalarField;
                object      T.orig;
            }}
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
            
            dimensions      [0 0 0 1 0 0 0];
            
            internalField   uniform 300;
            
            boundaryField
            {{
                #includeEtc "caseDicts/setConstraintTypes"

                walls
                {{
                    type            zeroGradient;
                }}

                "ball.*"
                {{
                    type            zeroGradient;
                }}

                
                outlet
                {{
                    type            zeroGradient;
                }}

                tank
                {{
                    type            zeroGradient;
                }}
            }}

            // ************************************************************************* //
            """
        else:
            return """

            FoamFile
            {
                version     2.0;
                format      ascii;
                class       volScalarField;
                object      T.orig;
            }
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            dimensions      [0 0 0 1 0 0 0];

            internalField   uniform 300;

            boundaryField
            {
                //- Set patchGroups for constraint patches
                #includeEtc "caseDicts/setConstraintTypes"

                "ball.*"
                {
                    type            zeroGradient;
                }
            }"""


    def generate_u(self, patch_name, explosive_active):
        if explosive_active:
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*/
            FoamFile
            {{
                version     2.0;
                format      ascii;
                class       volVectorField;
                object      U.orig;
            }}
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
            
            dimensions      [0 1 -1 0 0 0 0];
            
            internalField   uniform (0 0 0);
            
            boundaryField
            {{
                #includeEtc "caseDicts/setConstraintTypes"

                walls
                {{
                    type            slip;
                }}

                "ball.*"
                {{
                    type            movingWallVelocity;
                    value           $internalField;
                }}


                outlet
                {{
                    type            zeroGradient;
                }}

                tank
                {{
                    type            slip;
                }}
            }}

            // ************************************************************************* //
            """
        else:
            return """
            FoamFile
            {
                version     2.0;
                format      ascii;
                class       volVectorField;
                object      U.orig;
            }
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            dimensions      [0 1 -1 0 0 0 0];

            internalField   uniform (0 0 0);

            boundaryField
            {
                //- Set patchGroups for constraint patches
                #includeEtc "caseDicts/setConstraintTypes"

                "ball.*"
                {
                    type            movingWallVelocity;
                    value           $internalField;
                }
            }"""

